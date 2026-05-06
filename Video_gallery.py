import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
from datetime import datetime
import os
import sys
import json
import sqlite3
import threading
import time
try:
    import RPi.GPIO as GPIO
except:
    ...

THUMB_SIZE = (150, 100)

class VideoThumbnailItem(tk.Frame):
    def __init__(self, parent, video_path, index, app, **kw):
        super().__init__(parent, **kw)
        self.app = app
        self.index = index
        self.video_path = video_path
        self.selected = False

        # Generate thumbnail from video
        thumb_img = self.generate_thumbnail()
        self.thumb_tk = ImageTk.PhotoImage(thumb_img)

        # Checkbox
        self.var = tk.BooleanVar(value=False)
        self.chk = tk.Checkbutton(self, variable=self.var,
                                  command=self.on_checkbox_toggle,
                                  bg=self.app.palette['item_bg'],
                                  activebackground=self.app.palette['item_bg'],
                                  selectcolor=self.app.palette['item_bg'],
                                  bd=0)
        self.chk.pack(side="left", padx=(6,4))

        # Thumbnail
        self.img_label = tk.Label(self, image=self.thumb_tk,
                                  bg=self.app.palette['item_bg'])
        self.img_label.pack(side="left", padx=4, pady=6)

        # Video info
        info_frame = tk.Frame(self, bg=self.app.palette['item_bg'])
        info_frame.pack(side="left", padx=4)
        
        filename = os.path.basename(video_path)
        tk.Label(info_frame, text=filename, bg=self.app.palette['item_bg'],
                fg=self.app.palette['fg'], font=("Arial", 9, "bold")).pack(anchor="w")
        
        # Get video duration
        duration = self.get_video_duration()
        tk.Label(info_frame, text=f"Duration: {duration}s", bg=self.app.palette['item_bg'],
                fg=self.app.palette['fg'], font=("Arial", 8)).pack(anchor="w")

        # Bind clicks
        self.bind("<Button-1>", self.on_click)
        self.img_label.bind("<Button-1>", self.on_click)
        self.bind("<Control-Button-1>", self.on_ctrl_click)
        self.img_label.bind("<Control-Button-1>", self.on_ctrl_click)

        self.img_label.bind("<Double-Button-1>", self.video_player)

        self.configure_highlight()

    def video_player(self, event=None):

        try:
            # Use system default player
            import subprocess
            if os.name == 'nt':  # Windows
                os.startfile(self.video_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open',self.video_path])
            else:  # Linux/Raspberry Pi
                subprocess.call(['xdg-open',self.video_path])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot play video: {e}")


    def generate_thumbnail(self):
        """Generate thumbnail from first frame of video"""
        try:
            # Wait a bit if file was just created
            if os.path.exists(self.video_path):
                time.sleep(0.5)  # Give time for file to be fully written
            
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                raise Exception("Cannot open video")
            
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                pil_img.thumbnail(THUMB_SIZE)
                return pil_img
        except Exception as e:
            print(f"Thumbnail generation error: {e}")
        
        # Fallback: black placeholder
        return Image.new('RGB', THUMB_SIZE, color='black')

    def get_video_duration(self):
        """Get video duration in seconds"""
        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                return 0
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            
            if fps > 0 and frame_count > 0:
                return round(frame_count / fps, 1)
        except Exception as e:
            print(f"Duration detection error: {e}")
        return 0

    def configure_highlight(self):
        if self.selected:
            self.config(bg=self.app.palette['item_selected_bg'],
                       highlightbackground=self.app.palette['item_selected_border'],
                       highlightthickness=2, bd=0)
            self.chk.config(bg=self.app.palette['item_selected_bg'],
                           selectcolor=self.app.palette['item_selected_bg'])
            self.img_label.config(bg=self.app.palette['item_selected_bg'])
        else:
            self.config(bg=self.app.palette['item_bg'],
                       highlightbackground=self.app.palette['item_border'],
                       highlightthickness=1, bd=0)
            self.chk.config(bg=self.app.palette['item_bg'],
                           selectcolor=self.app.palette['item_bg'])
            self.img_label.config(bg=self.app.palette['item_bg'])

    def on_checkbox_toggle(self):
        if self.var.get():
            self.app.select_item(self, add=True)
        else:
            self.app.unselect_item(self)

    def on_click(self, event=None):
        self.app.on_item_click(self, ctrl=False)

    def on_ctrl_click(self, event=None):
        self.app.on_item_click(self, ctrl=True)


class VideoCaptureApp:
    def __init__(self, root):
        self.root = root
        if isinstance(root, tk.Tk):
            self.root.title("Video Capture App")
            self.root.attributes("-fullscreen", True)
        else:
            self.root.config(bg="#000000")
        
        def enable_fullscreen(retries=5):
            if retries == 0:
                return
            self.root.attributes("-fullscreen", True)
            if not self.root.attributes("-fullscreen"):
                self.root.after(200, lambda: enable_fullscreen(retries-1))

        self.root.after_idle(enable_fullscreen)

        self.dark = tk.BooleanVar(value=True)
        self.palette = {}
        self.set_palette()

        # State
        self.items = []
        self.selected = set()
        self.recording = False
        self.video_writer = None
        self.use_picamera = False
        self.camera = None
        self.picamera = None
        self.recording_start_time = None

        # Get settings from command line - ONLY video_location
        if len(sys.argv) > 2:
            self.patient_id = sys.argv[1]
            self.settings = json.loads(sys.argv[2])
        else:
            self.patient_id = None
            self.settings = {'video_location': 'static/videos'}
        
        if not self.settings:
            self.settings = {'video_location': 'static/videos'}

        # Ensure video directory exists
        os.makedirs(self.settings['video_location'], exist_ok=True)

        # Build UI
        self.create_ui()
        
        try:
            if not os.path.exists('dbs/settings.db'):
                return None

            conn = sqlite3.connect('dbs/settings.db')
            c = conn.cursor()

            c.execute("SELECT * FROM settings WHERE id=1")
            row = c.fetchone()
            conn.close()
            if not row:
                return None
            row = list(row)
            try:
                row[1]=json.loads(row[1])
            except:
                row[1]=[]

            self.settings_data = {
                "id": row[0],
                "categories": row[1],
                "video_format": row[2],
                "video_location": row[3],
                "image_format": row[4],
                "image_location": row[5],
                "audio_format": row[6],
                "audio_location": row[7],
                "streamresol": row[8],
                "imageresol": row[9],
                "videoresol": row[10],
                "exposure": row[11],
                "awb": row[12],
                "rotate": row[13]
            }
            self.streamsize = self.settings_data["streamresol"].split("x")
            self.rotate_to = self.settings_data["rotate"]

        except sqlite3.Error:
            return "png"

        # Initialize camera
        self.init_camera()
        
        try:
            GPIO.setmode(GPIO.BCM)
            self.SWITCH_PIN = 26
            GPIO.setup(self.SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except:
            print('Raspberry pi needed')

        
        # Getting Patient Date
        if len(sys.argv) > 1:
            id_for_get_data = int(sys.argv[1])
        try:
            self.conn = sqlite3.connect('dbs/patient_hospital.db')
            self.cursor = self.conn.cursor()

            self.cursor.execute("""
                SELECT first_name, middle_name, last_name, medical_record_no, port_no, gender FROM patient_full_details
                WHERE id = ?
            """, (id_for_get_data,))

            self.row_for_patient_data = self.cursor.fetchone()
            self.conn.close()
            print(self.row_for_patient_data)

        except Exception as e:
            print("something went error")

        # Database connection
        try:
            self.conn = sqlite3.connect("dbs/patient_hospital.db")
            self.cursor = self.conn.cursor()
        except:
            self.conn = None
            self.cursor = None

        # Start video stream
        self.update_frame()

        if isinstance(self.root, tk.Tk):
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    

    def set_palette(self):
        if self.dark.get():
            self.palette = {
                'bg': "#111111", 'fg': "white",
                'top_bg': "#222222", 'panel_bg': "#1f1f1f",
                'item_bg': "#2b2b2b", 'item_border': "#444444",
                'item_selected_bg': "#274b35", 'item_selected_border': "#79c67b",
                'btn_bg': "#2f79f6", 'btn_fg': "white",
                'danger_btn_bg': "#c94a3f",
                'record_btn_bg': "#4CAF50", 'record_btn_fg': "white",
                'recording_btn_bg': "#f44336"
            }
        else:
            self.palette = {
                'bg': "#f0f0f0", 'fg': "black",
                'top_bg': "#e6e6e6", 'panel_bg': "#ffffff",
                'item_bg': "#ffffff", 'item_border': "#d0d0d0",
                'item_selected_bg': "#dfeadf", 'item_selected_border': "#5a9a5a",
                'btn_bg': "#1976d2", 'btn_fg': "white",
                'danger_btn_bg': "#e57373",
                'record_btn_bg': "#4CAF50", 'record_btn_fg': "white",
                'recording_btn_bg': "#f44336"
            }

    def create_ui(self):
        # Top bar
        top = tk.Frame(self.root, bg=self.palette['top_bg'], height=50)
        top.pack(side="top", fill="x")
        tk.Label(top, text="Video Capture App", font=("Arial", 16, "bold"),
                bg=self.palette['top_bg'], fg=self.palette['fg']).pack(side="left", padx=16)
        tk.Checkbutton(top, text="Dark Mode", variable=self.dark, command=self.toggle_theme,
                      bg=self.palette['top_bg'], fg=self.palette['fg'],
                      selectcolor=self.palette['top_bg']).pack(side="right", padx=12)

        # Main frame
        main = tk.Frame(self.root, bg=self.palette['bg'])
        main.pack(fill="both", expand=True)

        # Gallery (left)
        self.gallery_frame = tk.Frame(main, bg=self.palette['panel_bg'], width=350)
        self.gallery_frame.pack(side="left", fill="y", padx=10, pady=10)

        lbl = tk.Label(self.gallery_frame, text="Video Gallery", font=("Arial", 14, "bold"),
                      bg=self.palette['panel_bg'], fg=self.palette['fg'])
        lbl.pack(anchor="nw", pady=(0,8), padx=8)

        # Gallery buttons
        btns = tk.Frame(self.gallery_frame, bg=self.palette['panel_bg'])
        btns.pack(fill="x", padx=8, pady=(0,8))
        tk.Button(btns, text="Select All", command=self.select_all,
                 bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=2)
        tk.Button(btns, text="Clear", command=self.clear_selection,
                 bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=2)
        tk.Button(btns, text="Play", command=self.play_selected,
                 bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=2)

        # Scrollable gallery
        self.gallery_canvas = tk.Canvas(self.gallery_frame, bg=self.palette['panel_bg'],
                                       highlightthickness=0)
        self.gallery_scroll = tk.Scrollbar(self.gallery_frame, orient="vertical",
                                          command=self.gallery_canvas.yview)
        self.gallery_canvas.configure(yscrollcommand=self.gallery_scroll.set)

        self.scrollable_frame = tk.Frame(self.gallery_canvas, bg=self.palette['panel_bg'])
        self.scrollable_frame.bind("<Configure>",
                                   lambda e: self.gallery_canvas.configure(
                                       scrollregion=self.gallery_canvas.bbox("all")))
        self.gallery_canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")

        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        self.gallery_scroll.pack(side="right", fill="y")

        # Mouse wheel scrolling
        self.gallery_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.gallery_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.gallery_canvas.bind_all("<Button-5>", self._on_mousewheel)

        # Right side - Camera view
        right = tk.Frame(main, bg=self.palette['bg'])
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.video_label = tk.Label(right, bg=self.palette['bg'])
        self.video_label.pack(pady=10)

        # Record button
        self.record_btn = tk.Button(right, text="● Start Recording",
                                    command=self.toggle_recording,
                                    bg=self.palette['record_btn_bg'],
                                    fg=self.palette['record_btn_fg'],
                                    font=("Arial", 14, "bold"),
                                    width=20, height=2)
        self.record_btn.pack(pady=10)


        # Bottom bar - ALL BUTTONS ON LEFT SIDE
        bottom = tk.Frame(self.root, bg=self.palette['top_bg'], height=60)
        bottom.pack(side="bottom", fill="x")
        
        # Left side buttons
        tk.Button(bottom, text="Save Selected", command=self.save_selected,
                 bg="#4CAF50", fg=self.palette['btn_fg'], 
                 font=("Arial", 10, "bold")).pack(side="left", padx=12, pady=8)
        tk.Button(bottom, text="Delete Selected", command=self.delete_selected,
                 bg=self.palette['danger_btn_bg'], fg=self.palette['btn_fg']).pack(
                     side="left", padx=5, pady=8)
        tk.Button(bottom, text="Exit", command=self.on_close,
                 bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(
                     side="right", padx=5, pady=8)
        tk.Button(bottom, text="OD (Right Eye)", command=self.od_function,
                 bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(
                     side="left", padx=5, pady=8)
        tk.Button(bottom, text="OS (Left Eye)", command=self.os_function,
                 bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(
                     side="left", padx=5, pady=8)
        
        # setting os od flag
        self.flage_od_os = "OD"


    def _on_mousewheel(self, event):
        if event.num == 4:
            self.gallery_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.gallery_canvas.yview_scroll(1, "units")
        else:
            self.gallery_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def toggle_theme(self):
        self.set_palette()
        self.root.config(bg=self.palette['bg'])
        # Update all widgets - simplified for performance
        for item in self.items:
            item.configure_highlight()


    def init_camera(self):
        """Initialize camera - try picamera first, then regular camera"""
        try:
            from picamera2 import Picamera2
            self.picamera = Picamera2()
            config = self.picamera.create_preview_configuration(
                main={"size": (640, 480),"format": "RGB888"}
            )
            self.picamera.configure(config)

            self.picamera.start()
            self.use_picamera = True
        except:
            try:
                self.camera = cv2.VideoCapture(0)
                if not self.camera.isOpened():
                    raise Exception("Camera not found")
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.use_picamera = False
            except Exception as e:
                messagebox.showerror("Error", f"No camera found: {str(e)}")

    def get_frame(self):
        """Get frame from camera"""
        if self.use_picamera:
            frame = self.picamera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            ret, frame = self.camera.read()
            if not ret:
                return None

        if frame is not None:
            
            # Display frame
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Resize for display (lighter on Pi)
            frame = cv2.resize(frame, ((int(self.streamsize[0])+0), (int(self.streamsize[1])-28)))
            if str(self.settings_data["rotate"]) == '90':
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                frame = cv2.resize(frame, (int(self.streamsize[1]), int(self.streamsize[1])-28))
            elif str(self.settings_data["rotate"]) == '180':
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif str(self.settings_data["rotate"]) == '270':
                frame = cv2.rotate(frame, cv2.ROTATE_270_CLOCKWISE)
                frame = cv2.resize(frame, (int(self.streamsize[1]), int(self.streamsize[1])-28))
            elif str(self.settings_data["rotate"]) == '0':
                ...
            else:
                print("Eat Five Star Do Nothing")
                
            
            # Get the current system time
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Overlay the time on the frame
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_color = (255, 255, 255)  # White text
            font_scale = 0.6
            thickness = 1
            position = (10, 30)  # Top-left corner
            
            needed_text = " ".join(
                [str(current_time)] + [str(value) for value in self.row_for_patient_data[:6]] + [str(self.flage_od_os)]
            )

            # Put the text on the frame
            frame = cv2.putText(frame, needed_text, position, font, font_scale, text_color, thickness, cv2.LINE_AA)
            
            # Write to video if recording

            if self.recording and self.video_writer is not None:
                self.video_writer.write(frame)
        return frame

    def check_gpio(self):
        #toggle_recording
        try:
            if GPIO.input(self.SWITCH_PIN) == GPIO.LOW:
                if not getattr(self, "_btn_lock", False):
                        self._btn_lock = True
                        self.toggle_recording()
                        self.root.after(250, lambda: setattr(self, "_btn_lock", False))

        except:
            print("raspberry missing")


    def update_frame(self):
        """Update video preview"""

        frame = self.get_frame()
        
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)
            
            self.check_gpio()
        
        self.root.after(30, self.update_frame)  # 30ms for lighter load

    def toggle_recording(self):
        """Start or stop recording"""
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start recording video - Use MP4/AVI format for better compatibility"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use .avi or .mp4 instead of .h 2 6 4 for better compatibility
        filename_only = f"video_{timestamp}.avi"
        filename = os.path.join(self.settings['video_location'], filename_only)
        
        # Verify directory exists
        os.makedirs(self.settings['video_location'], exist_ok=True)
        
        self.current_filename = filename_only
        self.current_full_path = filename

        frame = self.get_frame()

        if frame is None:
            messagebox.showerror("Error", "Cannot get frame from camera")
            return

        height, width = frame.shape[:2]

        # Use XVID codec for .avi (better compatibility than H 2 6 4 raw)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')

        try:
            self.video_writer = cv2.VideoWriter(filename, fourcc, 5.0, (width, height))

            if self.video_writer is None or not self.video_writer.isOpened():
                raise Exception("VideoWriter initialization failed")
            
            self.recording = True
            self.recording_start_time = time.time()
            self.record_btn.config(text="■ Stop Recording",
                                  bg=self.palette['recording_btn_bg'])
            
            print(f"Recording started: {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording: {e}")
            if self.video_writer:
                self.video_writer.release()
            self.video_writer = None

    def stop_recording(self):
        """Stop recording video and add thumbnail"""
        if self.video_writer is not None:
            # Release the writer properly
            self.video_writer.release()
            self.video_writer = None
            
            print(f"Recording stopped. Video saved to: {self.current_full_path}")
            
            # Wait a moment for file to be fully written
            time.sleep(0.5)
            
            # Verify file exists and has content
            if os.path.exists(self.current_full_path):
                file_size = os.path.getsize(self.current_full_path)
                print(f"Video file size: {file_size} bytes")
                
                if file_size > 0:
                    # Add to gallery thumbnail in a separate thread to avoid blocking
                    threading.Thread(target=self.add_video_thumbnail_async, 
                                   args=(self.current_full_path,), 
                                   daemon=True).start()
                else:
                    messagebox.showwarning("Warning", "Video file is empty")
            else:
                messagebox.showerror("Error", f"Video file not found: {self.current_full_path}")
        
        self.recording = False
        self.recording_start_time = None
        self.record_btn.config(text="● Start Recording",
                              bg=self.palette['record_btn_bg'])

    def add_video_thumbnail_async(self, video_path):
        """Add video thumbnail to gallery (called from thread)"""
        # Use after() to safely update GUI from thread
        self.root.after(0, self.add_video_thumbnail, video_path)

    def append_video_to_db(self, patient_id, filename_only):
        """Add video paths to database"""
        if not self.conn or not self.cursor:
            return
            
        try:
            self.cursor.execute(
                "SELECT Video FROM patient_full_details WHERE id = ?",
                (patient_id,)
            )
            row = self.cursor.fetchone()

            if row and row[0]:
                videos = json.loads(row[0])
            else:
                videos = []

            videos.extend(filename_only)

            self.cursor.execute(
                "UPDATE patient_full_details SET Video = ? WHERE id = ?",
                (json.dumps(videos), patient_id)
            )
            self.conn.commit()
        except Exception as e:
            print(f"Database error: {e}")

    def add_video_thumbnail(self, video_path):
        """Add video thumbnail to gallery"""
        idx = len(self.items)
        item = VideoThumbnailItem(self.scrollable_frame, video_path, idx, app=self,
                                  bg=self.palette['item_bg'])
        item.pack(anchor="nw", fill="x", padx=6, pady=3)
        self.items.append(item)

    def on_item_click(self, item, ctrl=False):
        if ctrl:
            if item in self.selected:
                self.unselect_item(item)
            else:
                self.select_item(item, add=True)
        else:
            self.clear_selection()
            self.select_item(item, add=False)

    def select_item(self, item, add=False):
        if not add:
            self.clear_selection()
        if item not in self.selected:
            self.selected.add(item)
            item.selected = True
            item.var.set(True)
            item.configure_highlight()

    def unselect_item(self, item):
        if item in self.selected:
            self.selected.remove(item)
        item.selected = False
        item.var.set(False)
        item.configure_highlight()

    def clear_selection(self):
        for it in list(self.selected):
            it.selected = False
            it.var.set(False)
            it.configure_highlight()
        self.selected.clear()

    def select_all(self):
        for it in self.items:
            self.select_item(it, add=True)

    def play_selected(self):
        """Play selected video in external player"""
        if not self.selected:
            messagebox.showinfo("Play", "No video selected")
            return
        
        item = list(self.selected)[0]
        try:
            # Use system default player
            import subprocess
            if os.name == 'nt':  # Windows
                os.startfile(item.video_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', item.video_path])
            else:  # Linux/Raspberry Pi
                subprocess.call(['xdg-open', item.video_path])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot play video: {e}")

    def delete_selected(self):
        """Delete selected videos"""
        if not self.selected:
            messagebox.showinfo("Delete", "No videos selected")
            return

        if not messagebox.askyesno("Confirm", "Delete selected video(s)?"):
            return

        selected_items = list(self.selected)
        self.clear_selection()

        for item in selected_items:
            try:
                # Delete file
                if os.path.exists(item.video_path):
                    os.remove(item.video_path)
                
                # Remove from UI
                item.destroy()
                self.items.remove(item)
            except Exception as e:
                print(f"Error deleting {item.video_path}: {e}")

        # Reindex
        for i, it in enumerate(self.items):
            it.index = i

        messagebox.showinfo("Delete", f"Deleted {len(selected_items)} video(s)")

    def save_selected(self):
        """Save selected videos to database"""
        if not self.selected:
            messagebox.showinfo("Save", "No videos selected to save")
            return
        
        if not self.patient_id:
            messagebox.showwarning("Warning", "No patient ID provided. Videos are saved to disk only.")
            return
        
        selected_items = list(self.selected)
        video_paths = [os.path.basename(item.video_path) for item in selected_items]
        
        try:
            self.append_video_to_db(self.patient_id, video_paths)
            messagebox.showinfo("Save", f"Successfully saved {len(video_paths)} video(s) to database!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save to database: {e}")


    def od_function(self):
        self.flage_od_os = "OD"

    def os_function(self):
        self.flage_od_os = "OS"

    def on_close(self):
        """Clean up on exit"""
        self.stop_recording()
        
        if self.use_picamera and self.picamera is not None:
            self.picamera.stop()
            self.picamera.close()
        elif self.camera is not None:
            self.camera.release()
        
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
        
        cv2.destroyAllWindows()
        self.root.destroy()


def create_video_widget(parent):
    """Embed video capture in parent frame"""
    app = VideoCaptureApp(parent)
    return app


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCaptureApp(root)
    root.mainloop()
