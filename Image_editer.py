#!/usr/bin/env python3
"""
Standalone Image Editor
Usage: python3 editor.py img/path.png
"""

import sys
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps


class ImageEditor:
    def __init__(self, image_path, image_storing_path):
        self.root = tk.Tk()
        self.root.withdraw()  # Hide main window
        
        try:
            self.img_ref = Image.open(image_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")
            sys.exit(1)
        
        self.open_editor()
    
    def open_editor(self):
        """
        Enhanced editor function using lite_image_editor.py functionality
        """
        
        orig = self.img_ref.copy().convert("RGB")
        history = [orig.copy()]
        hist_idx = [0]  # Mutable container for history index
        
        win = tk.Toplevel(self.root)
        win.title("Lite Image Editor")
        win.attributes("-fullscreen", True)
        win.bind("<Escape>", lambda e: win.attributes("-fullscreen", False))
        win.bind("<F11>", lambda e: win.attributes("-fullscreen", True))
        win.config(bg="#1a1a1a")
        
        # Variables for adjustments
        bright_var = tk.DoubleVar(value=1.0)
        contrast_var = tk.DoubleVar(value=1.0)
        sat_var = tk.DoubleVar(value=1.0)
        
        # Top bar
        top = tk.Frame(win, bg="#2d2d2d", height=40)
        top.pack(fill="x")
        tk.Label(top, text="Image Editor", font=("Arial", 12, "bold"),
                bg="#2d2d2d", fg="#fff").pack(side="left", padx=10)
        tk.Label(top, text="F11: Fullscreen | Esc: Exit Fullscreen",
                font=("Arial", 8), bg="#2d2d2d", fg="#aaa").pack(side="left", padx=20)
        status = tk.Label(top, text="Ready", bg="#2d2d2d", fg="#fff", anchor="e")
        status.pack(side="right", padx=10)
        
        # Main container
        main = tk.Frame(win, bg="#1a1a1a")
        main.pack(fill="both", expand=True)
        
        # Left panel - Filters and Transforms
        left = tk.Frame(main, bg="#2d2d2d", width=180)
        left.pack(side="left", fill="y", padx=5, pady=5)
        left.pack_propagate(False)
        
        tk.Label(left, text="Filters", font=("Arial", 11, "bold"),
                bg="#2d2d2d", fg="#fff").pack(pady=10)
        
        # Tooltip class
        class ToolTip:
            def __init__(self, widget, text):
                self.widget = widget
                self.text = text
                self.tooltip = None
                self.widget.bind("<Enter>", self.show)
                self.widget.bind("<Leave>", self.hide)
            
            def show(self, event=None):
                x, y, _, _ = self.widget.bbox("insert")
                x += self.widget.winfo_rootx() + 25
                y += self.widget.winfo_rooty() + 25
                
                self.tooltip = tk.Toplevel(self.widget)
                self.tooltip.wm_overrideredirect(True)
                self.tooltip.wm_geometry(f"+{x}+{y}")
                
                label = tk.Label(self.tooltip, text=self.text, bg="#ffffe0", 
                               fg="#000", relief="solid", borderwidth=1,
                               font=("Arial", 9))
                label.pack()
            
            def hide(self, event=None):
                if self.tooltip:
                    self.tooltip.destroy()
                    self.tooltip = None
        
        # Load custom icons
        def load_icon(path, size=(32, 32)):
            """Load and resize icon image"""
            try:
                img = Image.open(path).convert("RGBA")
                img.thumbnail(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Icon load error for {path}: {e}")
                return None
        
        # Update these paths to your icon locations
        icon_paths = {
            'original': 'static/original.png',
            'gray': 'static/gray.png',
            'sepia': 'static/sepia.png',
            'vintage': 'static/vintage.png',
            'invert': 'static/invert.png',
            'red': 'static/red.png',
            'green': 'static/green.png',
            'blue': 'static/blue.png',
            'rotate': 'static/rotate.png',
            'flip_h': 'static/h_flip.png',
            'flip_v': 'static/v_flip.png',
        }
        
        # Load icons
        icons = {}
        for key, path in icon_paths.items():
            icons[key] = load_icon(path)
        
        # Center - Preview
        center = tk.Frame(main, bg="#1a1a1a")
        center.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Canvas for image preview
        canvas = tk.Canvas(center, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        # Zoom / pan state
        zoom_level = [1.0]
        tk_preview = [None]
        canvas_img = [None]
        pan_start = [0, 0]

        
        def apply_filter(ftype):
            # Get the current adjusted image (with brightness/contrast/saturation)
            current = get_current_image()
            
            if ftype is None:
                result = current.copy()

            elif ftype == 'gray':
                result = ImageOps.grayscale(current).convert("RGB")

            elif ftype == 'sepia':
                gray = ImageOps.grayscale(current)
                result = ImageOps.colorize(gray, "#704214", "#C0A080").convert("RGB")

            elif ftype == 'vintage':
                gray = ImageOps.grayscale(current)
                tmp = ImageOps.colorize(gray, "#704214", "#C0A080")
                result = ImageEnhance.Contrast(tmp).enhance(0.9).convert("RGB")

            elif ftype == 'invert':
                result = ImageOps.invert(current.convert("RGB"))

            elif ftype in ('red', 'green', 'blue'):
                r, g, b = current.convert("RGB").split()

                if ftype == 'red':
                    result = Image.merge("RGB", (r, r, r))
                elif ftype == 'green':
                    result = Image.merge("RGB", (g, g, g))
                else:  # blue
                    result = Image.merge("RGB", (b, b, b))

            else:
                return  # safety

            # Add to history and reset adjustments
            add_to_history(result)
            reset_sliders()
            show_preview()
            status.config(text=f"Applied: {ftype or 'original'}")

        # Filter definitions with icon keys and names
        filters = [
            ('original', "Original", lambda: reset_all()),
            ('gray', "Grayscale", lambda: apply_filter('gray')),
            ('sepia', "Sepia", lambda: apply_filter('sepia')),
            ('vintage', "Vintage", lambda: apply_filter('vintage')),
            ('invert', "Invert", lambda: apply_filter('invert')),
            ('red', "Red Channel", lambda: apply_filter('red')),
            ('green', "Green Channel", lambda: apply_filter('green')),
            ('blue', "Blue Channel", lambda: apply_filter('blue')),
        ]
        
        # Create filter buttons with icons or text fallback
        for icon_key, name, cmd in filters:
            icon_img = icons.get(icon_key)
            if icon_img:
                # Use image icon
                btn = tk.Button(left, image=icon_img, command=cmd, bg="#4a4a4a",
                               width=120, height=40, relief="flat", bd=0,
                               activebackground="#5a5a5a")
                btn.image = icon_img  # Keep reference to prevent garbage collection
            else:
                # Fallback to text if icon not found
                btn = tk.Button(left, text=name, command=cmd, bg="#4a4a4a",
                               fg="#fff", width=15)
            btn.pack(pady=2)
            ToolTip(btn, name)
        
        tk.Label(left, text="Transform", font=("Arial", 11, "bold"),
                bg="#2d2d2d", fg="#fff").pack(pady=(15, 5))
        
        def rotate(angle):
            current = get_current_image()
            result = current.rotate(angle, expand=True, fillcolor='white')
            add_to_history(result)
            show_preview()
            status.config(text=f"Rotated {angle}°")
        
        def flip(direction):
            current = get_current_image()
            if direction == 'h':
                result = current.transpose(Image.FLIP_LEFT_RIGHT)
            else:
                result = current.transpose(Image.FLIP_TOP_BOTTOM)
            add_to_history(result)
            show_preview()
            status.config(text=f"Flipped {direction}")
        
        # Transform buttons with icons
        transforms = [
            ('rotate', "Rotate 90°", lambda: rotate(90)),
            ('flip_h', "Flip Horizontal", lambda: flip('h')),
            ('flip_v', "Flip Vertical", lambda: flip('v')),
        ]
        
        for icon_key, name, cmd in transforms:
            icon_img = icons.get(icon_key)
            if icon_img:
                # Use image icon
                btn = tk.Button(left, image=icon_img, command=cmd, bg="#4a4a4a",
                               width=120, height=40, relief="flat", bd=0,
                               activebackground="#5a5a5a")
                btn.image = icon_img  # Keep reference
            else:
                # Fallback to text if icon not found
                btn = tk.Button(left, text=name, command=cmd, bg="#4a4a4a",
                               fg="#fff", width=15)
            btn.pack(pady=2)
            ToolTip(btn, name)
        

        
        
        def show_preview():
            img = get_current_image()

            # apply zoom
            w, h = img.size
            zw = int(w * zoom_level[0])
            zh = int(h * zoom_level[0])

            display = img.resize((zw, zh), Image.Resampling.LANCZOS)

            tk_preview[0] = ImageTk.PhotoImage(display)

            canvas.delete("all")

            canvas_img[0] = canvas.create_image(
                canvas.winfo_width() // 2,
                canvas.winfo_height() // 2,
                image=tk_preview[0],
                anchor="center"
            )

        def zoom(event):
            if event.delta > 0:
                zoom_level[0] *= 1.1
            else:
                zoom_level[0] /= 1.1

            zoom_level[0] = max(0.2, min(zoom_level[0], 5))

            show_preview()

        canvas.bind("<Button-4>", lambda e: zoom(type("e", (), {"delta": 120})))
        canvas.bind("<Button-5>", lambda e: zoom(type("e", (), {"delta": -120})))

        def start_pan(event):
            pan_start[0] = event.x
            pan_start[1] = event.y

        def do_pan(event):
            dx = event.x - pan_start[0]
            dy = event.y - pan_start[1]

            canvas.move(canvas_img[0], dx, dy)

            pan_start[0] = event.x
            pan_start[1] = event.y

        canvas.bind("<ButtonPress-1>", start_pan)
        canvas.bind("<B1-Motion>", do_pan)
        
        win.bind("=", lambda e: zoom(type("e", (), {"delta": 120})))   #key board zoom +
        win.bind("-", lambda e: zoom(type("e", (), {"delta": -120})))    # -

        canvas.bind("<Configure>", lambda e: show_preview())
        
        
        def reset_zoom():
            zoom_level[0] = 1.0
            show_preview()

        
        def get_current_image():
            """Get current image from history with adjustments applied"""
            if hist_idx[0] < len(history):
                base = history[hist_idx[0]].copy()
            else:
                base = orig.copy()
            
            # Apply adjustments
            img = ImageEnhance.Brightness(base).enhance(bright_var.get())
            img = ImageEnhance.Contrast(img).enhance(contrast_var.get())
            img = ImageEnhance.Color(img).enhance(sat_var.get())
            
            return img
        
        def add_to_history(img):
            """Add image to history (keep last 5 for memory efficiency)"""
            history[:] = history[:hist_idx[0] + 1]
            history.append(img.copy())
            if len(history) > 5:
                history.pop(0)
            else:
                hist_idx[0] += 1
        
        def adjust(*args):
            """Real-time adjustment preview"""
            show_preview()
        
        # Right panel - Adjustments
        right = tk.Frame(main, bg="#2d2d2d", width=220)
        right.pack(side="right", fill="y", padx=5, pady=5)
        right.pack_propagate(False)
        
        tk.Label(right, text="Adjustments", font=("Arial", 11, "bold"),
                bg="#2d2d2d", fg="#fff").pack(pady=10)
        
        def make_slider(parent, label, var, color):
            fr = tk.Frame(parent, bg="#2d2d2d")
            fr.pack(padx=10, pady=3)
            tk.Label(fr, text=label, bg="#2d2d2d", fg=color,
                    font=("Arial", 9, "bold")).pack(anchor="w")
            tk.Scale(fr, from_=0, to=2, resolution=0.05, orient="horizontal",
                    variable=var, command=adjust, bg="#2d2d2d", fg="#fff",
                    length=190, showvalue=True).pack()
        
        make_slider(right, "Brightness", bright_var, "#ffff88")
        make_slider(right, "Contrast", contrast_var, "#88ffff")
        make_slider(right, "Saturation", sat_var, "#ff88ff")
        
        def reset_sliders():
            bright_var.set(1.0)
            contrast_var.set(1.0)
            sat_var.set(1.0)
        
        def reset_all():
            history[:] = [orig.copy()]
            hist_idx[0] = 0
            reset_sliders()
            show_preview()
            status.config(text="Reset to original")
        
        tk.Button(right, text="Reset All", command=reset_all,
                 bg="#c94a3f", fg="white", width=18).pack(pady=10)
        
        # Bottom bar
        bottom = tk.Frame(win, bg="#2d2d2d", height=35)
        bottom.pack(fill="x")
        
        def undo():
            if hist_idx[0] > 0:
                hist_idx[0] -= 1
                reset_sliders()
                show_preview()
                status.config(text="Undo")
        
        def save_and_close():
            from tkinter import filedialog
            current = get_current_image()
            
            # Ask where to save
            path = sys.argv[1]
            
            if path:
                try:
                    current.save(path, quality=95)
                    win.destroy()
                    self.root.quit()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save: {e}")
        
        def cancel_close():
            win.destroy()
            self.root.quit()
        
        tk.Button(bottom, text="⟲ Undo", command=undo, bg="#4a4a4a",
                 fg="#fff", width=8).pack(side="left", padx=5, pady=2)
        
        tk.Button(bottom, text="Save Changes", command=save_and_close,
                 bg="#2f79f6", fg="white", padx=20, pady=2,
                 font=("Arial", 10, "bold")).pack(side="right", padx=5)
        tk.Button(bottom, text="Cancel", command=cancel_close,
                 bg="#c94a3f", fg="white", padx=20, pady=2,
                 font=("Arial", 10, "bold")).pack(side="right", padx=5)
        
        # Initial preview
        show_preview()
    
    def run(self):
        self.root.mainloop()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 editor.py img/path.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    image_storing_path = sys.argv[2]
    editor = ImageEditor(image_path, image_storing_path)
    editor.run()


if __name__ == "__main__":
    main()
