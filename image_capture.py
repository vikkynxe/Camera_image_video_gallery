# camera_gallery_improved.py
from PIL import Image, ImageTk, ImageEnhance, ImageOps
import cv2
import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
from datetime import datetime
import os
import sys
try:
    import RPi.GPIO as GPIO
except:
    ...
import time
import random
import subprocess
import gc
import threading
import queue

THUMB_SIZE = (310, 233)

running_or_passing = False
flag_for_image_viewer = False

class ThumbnailItem(tk.Frame):
    def __init__(self, parent, pil_image, index, app, **kw):
        super().__init__(parent, **kw)
        self.app = app
        self.index = index
        self.img_ref = pil_image.copy()   # full-size PIL
        self.selected = False

        # thumbnail image
        tn = pil_image.copy()
        tn.thumbnail(THUMB_SIZE)
        self.thumb_tk = ImageTk.PhotoImage(tn)

        # checkbox on left
        self.var = tk.BooleanVar(value=False)
        self.chk = tk.Checkbutton(self, variable=self.var,
                                  command=self.on_checkbox_toggle,
                                  bg=self.app.palette['item_bg'],
                                  activebackground=self.app.palette['item_bg'],
                                  selectcolor=self.app.palette['item_bg'],
                                  bd=0)
        self.chk.pack(side="left", padx=(6,4))

        # image label
        self.img_label = tk.Label(self, image=self.thumb_tk,
                                  bg=self.app.palette['item_bg'])
        self.img_label.pack(side="left", padx=4, pady=6)

        # make whole frame clickable
        self.bind("<Button-1>", self.on_click)
        self.img_label.bind("<Button-1>", self.on_click)
        # Ctrl and Shift variants (bind them also)
        self.bind("<Control-Button-1>", self.on_ctrl_click)
        self.img_label.bind("<Control-Button-1>", self.on_ctrl_click)
        self.bind("<Shift-Button-1>", self.on_shift_click)
        self.img_label.bind("<Shift-Button-1>", self.on_shift_click)
        
        self.img_label.bind("<Double-Button-1>", self.openning_default_img_viewer)

        # visual border
        self.configure_highlight()
    
#========================================================================================================================
    # Opening image

    def openning_default_img_viewer(self, event=None):
        self.image = self.img_ref.copy().convert("RGB")

        save_path = "tempro/view.png"
        self.image.save(save_path)

        subprocess.Popen(["xdg-open", save_path])
        #subprocess.Popen(["eog", "--fullscreen", save_path])
        #subprocess.Popen(["python3","img_viewer.py", save_path])
        #subprocess.Popen(["lximage-qt", "--fullscreen", save_path])


    def open_image(self, event=None):
        
        self.image = self.img_ref.copy().convert("RGB")
        self.zoom = 1.0
        self.min_zoom = 0.2
        self.max_zoom = 5.0
        
        try:
            self.app.root.grab_release()
        except:
            pass
            
        
        # Create a new popup window
        self.top = tk.Toplevel(self.app.root)
        self.top.title("Image Viewer")
        self.top.attributes("-zoomed", True)
        self.top.focus_force()

        self.top.bind("<Escape>", lambda e: self.top.destroy())

        self.frame = tk.Frame(self.top)
        self.frame.pack(fill="both", expand=True)

        # Canvas + scrollbars
        self.canvas = tk.Canvas(self.frame, bg="black")
        self.hbar = tk.Scrollbar(self.frame, orient="horizontal", command=self.canvas.xview)
        self.vbar = tk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        self.hbar.pack(side="bottom", fill="x")
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Bindings
        self.canvas.bind("<MouseWheel>", self.zoom_image)
        self.canvas.bind("<Button-4>", self.zoom_image)
        self.canvas.bind("<Button-5>", self.zoom_image)
        self.canvas.bind("<ButtonPress-1>", self.pan_start)
        self.canvas.bind("<B1-Motion>", self.pan_move)

        # Display initial image
        self.display_image()
        global flag_for_image_viewer
        flag_for_image_viewer = True

        close_btn = tk.Button(self.top, text="Close", command=self.close_image_window)
        close_btn.pack(side="bottom", pady=5)
        

    def display_image(self):
        width = int(self.image.width * self.zoom)
        height = int(self.image.height * self.zoom)
        resized = self.image.resize((width, height), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.canvas.config(scrollregion=self.canvas.bbox(self.image_id))


    def zoom_image(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        if getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4:
            new_zoom = self.zoom * 1.1
        else:
            new_zoom = self.zoom / 1.1

        if self.min_zoom <= new_zoom <= self.max_zoom:
            self.zoom = new_zoom
            self.display_image()


    def pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)


    def pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)


    def close_image_window(self):
        if hasattr(self, 'top') and self.top.winfo_exists():
            self.top.destroy()  # closes the Toplevel window
            global flag_for_image_viewer
            flag_for_image_viewer = False
#========================================================================================================================

    def configure_highlight(self):
        # visual state of selection
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
        # clicking checkbox toggles selection (sync)
        if self.var.get():
            self.app.select_item(self, add=True)
        else:
            self.app.unselect_item(self)

    def on_click(self, event=None):
        # plain click => single selection (clear others)
        self.app.on_item_click(self, ctrl=False, shift=False)

    def on_ctrl_click(self, event=None):
        self.app.on_item_click(self, ctrl=True, shift=False)

    def on_shift_click(self, event=None):
        self.app.on_item_click(self, ctrl=False, shift=True)

    def update_thumbnail(self):
        tn = self.img_ref.copy()
        tn.thumbnail(THUMB_SIZE)
        self.thumb_tk = ImageTk.PhotoImage(tn)
        self.img_label.config(image=self.thumb_tk)
        self.img_label.image = self.thumb_tk  # prevent GC

    def destroy(self):
        # clear references
        try:
            del self.thumb_tk
        except:
            pass
        super().destroy()


class CameraApp:

    def _on_mousewheel(self, event):
        global running_or_passing 
        global flag_for_image_viewer

        if running_or_passing or flag_for_image_viewer:
            return

        if event.num == 4:   # Linux scroll up
            self.gallery_canvas.yview_scroll(-1, "units")
        elif event.num == 5: # Linux scroll down
            self.gallery_canvas.yview_scroll(1, "units")
        else:  # Windows / Mac
            self.gallery_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
    
            
    def __init__(self, root):
        
        self.frame_queue = queue.Queue(maxsize=1)
        self.camera_running = True
        self.root = root
        if isinstance(root, tk.Tk):
            # Run as standalone window
            self.root.title("IS25 App")

        else:
            # Embedded mode (iframe-like)
            self.root.config(bg="#000000")


        self.dark = tk.BooleanVar(value=True)
        self.palette = {}
        self.set_palette()   # initialize palette

        # state
        self.items = []              # list of Thumbnail Item
        self.selected = set()        # set of Thumbnail Item
        self.last_selected_index = None

        # top bar
        top = tk.Frame(root, bg=self.palette['top_bg'], height=50)
        top.pack(side="top", fill="x")
        tk.Label(top, text="Camera Capture App", font=("Arial", 16, "bold"),
                 bg=self.palette['top_bg'], fg=self.palette['fg']).pack(side="left", padx=16)
        tk.Checkbutton(top, text="Dark Mode", variable=self.dark, command=self.toggle_theme,
                       bg=self.palette['top_bg'], fg=self.palette['fg'],
                       selectcolor=self.palette['top_bg']).pack(side="right", padx=12)

        # main frame
        main = tk.Frame(root, bg=self.palette['bg'])
        main.pack(fill="both", expand=True)

        # Gallery / left
        self.gallery_frame = tk.Frame(main, bg=self.palette['panel_bg'], width=300)
        self.gallery_frame.pack(side="left", fill="y", padx=10, pady=10)

        lbl = tk.Label(self.gallery_frame, text="Gallery", font=("Arial", 14, "bold"),
                       bg=self.palette['panel_bg'], fg=self.palette['fg'])
        lbl.pack(anchor="nw", pady=(0,8), padx=8)

        # action buttons for gallery
        btns = tk.Frame(self.gallery_frame, bg=self.palette['panel_bg'])
        btns.pack(fill="x", padx=8, pady=(0,8))
        tk.Button(btns, text="Select All", command=self.select_all, bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=4)
        tk.Button(btns, text="Clear", command=self.clear_selection, bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=4)
        tk.Button(btns, text="Edit Selected", command=self.open_editor, bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=4)

        # scroll area
        # Enable mouse wheel scrolling
        # Create canvas
        self.gallery_canvas = tk.Canvas(self.gallery_frame, bg=self.palette['panel_bg'], highlightthickness=0)
        self.gallery_scroll = tk.Scrollbar(self.gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
        self.gallery_canvas.configure(yscrollcommand=self.gallery_scroll.set)

        self.scrollable_frame = tk.Frame(self.gallery_canvas, bg=self.palette['panel_bg'])
        self.scrollable_frame.bind("<Configure>", lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))
        self.gallery_canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")

        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        self.gallery_scroll.pack(side="right", fill="y")

        # now bind mouse scroll
        self.gallery_canvas.bind("<Button-4>", self._on_mousewheel)     # Linux scroll up
        self.gallery_canvas.bind("<Button-5>", self._on_mousewheel)     # Linux scroll down


        # Right = camera view
        right = tk.Frame(main, bg=self.palette['bg'])
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.video_label = tk.Label(right, bg=self.palette['bg'])
        self.video_label.pack(pady=10)
        tk.Button(right, text="Capture", command=self.capture_image, bg=self.palette['capture_btn_bg'], fg=self.palette['capture_btn_fg'], font=("Arial", 14)).pack(pady=10)

        # bottom bar
        bottom = tk.Frame(root, bg=self.palette['top_bg'], height=60)
        bottom.pack(side="bottom", fill="x")
        tk.Button(bottom, text="Save Selected", command=self.save_selected, bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=12, pady=8)
        tk.Button(bottom, text="Delete Selected", command=self.delete_selected, bg=self.palette['danger_btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=12, pady=8)

        tk.Button(bottom, text="OD (Right Eye)", command=self.od_function, bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=12, pady=8)
        tk.Button(bottom, text="OS (Left Eye)", command=self.os_function, bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="left", padx=12, pady=8)

        tk.Button(bottom, text="Exit", command=self.on_close, bg=self.palette['btn_bg'], fg=self.palette['btn_fg']).pack(side="right", padx=12, pady=8)


        # setting os od flag
        self.flage_od_os = "OD"

        # Enable Full Screen
        def enable_fullscreen(retries=5):
            if retries == 0:
                return
            self.root.attributes("-fullscreen", True)
            if not self.root.attributes("-fullscreen"):
                self.root.after(200, lambda: enable_fullscreen(retries-1))

        self.root.after_idle(enable_fullscreen)
        

        # Get Data For streaming and storing reselution
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


        # Initializing Camera
        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            preview_config = self.picam2.create_preview_configuration(main={"format": "RGB888", "size": (1400 , 788)})
            
            self.picam2.configure(preview_config)
            if self.settings_data["awb"] == "Conjuntive":
                self.picam2.set_controls({
                    "AwbEnable": False,
                    "ColourGains": (1.6, 1.2)
                })
            self.picam2.start()
            self.use_picam = True
        except ImportError:
            print("Picamera2 not found, using OpenCV webcam...")
            self.cap = cv2.VideoCapture(0)
            self.use_picam = False
            

        # GPIO Setting Up 
        try:
            GPIO.setmode(GPIO.BCM)
            self.SWITCH_PIN = 26
            GPIO.setup(self.SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except:
            print('Raspberry pi needed')


        # Getting Patient Date
        if len(sys.argv) > 1:
            id_for_get_data = sys.argv[1]
        
        try:
            self.conn = sqlite3.connect('dbs/patient_hospital.db')
            self.cursor = self.conn.cursor()

            self.cursor.execute("""
                SELECT first_name, middle_name, last_name, medical_record_no, port_no, gender FROM patient_full_details
                WHERE id = ?
            """, (id_for_get_data,))

            self.row_for_patient_data = self.cursor.fetchone()
            self.conn.close()

        except Exception as e:
            self.row_for_patient_data =["first","middle","last","mrn","pn","mail"]
            print("something went error")


        # Starting Streaming 
        self.cam_thread = threading.Thread(target=self.camera_loop, daemon=True)
        self.cam_thread.start()
        self.update_frame()


        # ensure cleanup
        # Only set protocol if it's a real Tk window (not embedded frame)
        if isinstance(self.root, tk.Tk):
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)


    def set_palette(self):
        if getattr(self, "dark", None) and self.dark.get():
            self.palette = {
                'bg': "#111111", 'fg': "white",
                'top_bg': "#222222", 'panel_bg': "#1f1f1f",
                'item_bg': "#2b2b2b", 'item_border': "#444444",
                'item_selected_bg': "#274b35", 'item_selected_border': "#79c67b",
                'btn_bg': "#2f79f6", 'btn_fg': "white",
                'danger_btn_bg': "#c94a3f",
                'capture_btn_bg': "#4CAF50", 'capture_btn_fg': "white",
            }
        else:
            self.palette = {
                'bg': "#f0f0f0", 'fg': "black",
                'top_bg': "#e6e6e6", 'panel_bg': "#ffffff",
                'item_bg': "#ffffff", 'item_border': "#d0d0d0",
                'item_selected_bg': "#dfeadf", 'item_selected_border': "#5a9a5a",
                'btn_bg': "#1976d2", 'btn_fg': "white",
                'danger_btn_bg': "#e57373",
                'capture_btn_bg': "#4CAF50", 'capture_btn_fg': "white",
            }

    def toggle_theme(self):
        self.set_palette()
        # update top/root colors
        self.root.config(bg=self.palette['bg'])
        for widget in self.root.winfo_children():
            try:
                # top bar and bottom bar are frames
                widget.config(bg=self.palette.get('top_bg', self.palette['bg']))
                for c in widget.winfo_children():
                    try:
                        c_type = c.winfo_class().lower()
                        if c_type in ('button','label','checkbutton','frame'):
                            c.config(bg=self.palette.get('top_bg', self.palette['bg']), fg=self.palette['fg'])
                        else:
                            c.config(bg=self.palette.get('top_bg', self.palette['bg']))
                    except Exception:
                        pass
            except Exception:
                pass

        # gallery frame + scroll area
        self.gallery_frame.config(bg=self.palette['panel_bg'])
        self.gallery_canvas.config(bg=self.palette['panel_bg'])
        self.scrollable_frame.config(bg=self.palette['panel_bg'])
        self.gallery_scroll.config(bg=self.palette['panel_bg'], troughcolor=self.palette['panel_bg'])

        # update existing thumbnail items
        for item in self.items:
            item.chk.config(bg=self.palette['item_bg'], activebackground=self.palette['item_bg'], selectcolor=self.palette['item_bg'], fg=self.palette['fg'])
            item.img_label.config(bg=self.palette['item_bg'])
            item.app = self  # ensure app reference
            item.configure_highlight()


    def camera_loop(self):
        target_fps = 50
        frame_time = 1.0 / target_fps

        while self.camera_running:
            start_time = time.time()

            try:
                if self.use_picam:
                    frame = self.picam2.capture_array()
                else:
                    ret, frame = self.cap.read()
                    if not ret:
                        continue

                if not self.frame_queue.full():
                    self.frame_queue.put(frame)

            except Exception as e:
                print("Camera thread error:", e)

            # FPS control
            elapsed = time.time() - start_time
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def update_frame(self):
        try:
            flag_for_infunction = False
            global running_or_passing
            if running_or_passing:
                return
                    
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (int(self.streamsize[0]), int(self.streamsize[1])))
                if str(self.settings_data["rotate"]) == '90':
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                    frame = cv2.resize(frame, (int(self.streamsize[1]), int(self.streamsize[1])))
                elif str(self.settings_data["rotate"]) == '180':
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif str(self.settings_data["rotate"]) == '270':
                    frame = cv2.rotate(frame, cv2.ROTATE_270_CLOCKWISE)
                    frame = cv2.resize(frame, (int(self.streamsize[1]), int(self.streamsize[1])))
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


                #frame = cv2.resize(frame, (1320, 880))
                img = Image.fromarray(frame)
                tkimg = ImageTk.PhotoImage(img)
                self.video_label.imgtk = tkimg
                self.video_label.config(image=tkimg, bg=self.palette['bg'])
                try:
                    if GPIO.input(self.SWITCH_PIN) == GPIO.LOW:
                        if not getattr(self, "_btn_lock", False):
                            self._btn_lock = True
                            self.capture_image()
                            self.root.after(250, lambda: setattr(self, "_btn_lock", False))

                except:
                    ...
        except Exception as e:
                print("Frame error:", e)
        self.root.after(50, self.update_frame)


    def capture_image(self):
        flag_for_infunction = False
        try:
            frame = self.picam2.capture_array()
            if (frame is not None) and True:
                flag_for_infunction = True
        except:
            ret, frame = self.cap.read()
            if ret:
                flag_for_infunction = True
        if flag_for_infunction:
            if str(self.settings_data["rotate"]) == '90':
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif str(self.settings_data["rotate"]) == '180':
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif str(self.settings_data["rotate"]) == '270':
                frame = cv2.rotate(frame, cv2.ROTATE_270_CLOCKWISE)
            elif str(self.settings_data["rotate"]) == '0':
                ...
            else:
                print("Eat Five Star Do Nothing")
            folder_path = 'tempro'
            files = os.listdir(folder_path)
            for file in files:
                file_path = os.path.join(folder_path, file)

                if os.path.isfile(file_path):  # Check if it's a file, not a folder
                    os.remove(file_path)
                    print(f"Deleted: {file}")
                    
                    
            # --- Generate filename with datetime ---
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S"+str(random.randint(1, 100)
))
            filename = f"img_{timestamp}.{self.settings_data['image_format']}"
            filepath = os.path.join("tempro", filename)

            # --- Ensure folder exists ---
            if not os.path.exists("tempro"):
                os.makedirs("tempro")
            
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

            # --- Save to folder ---
            cv2.imwrite(filepath, frame)
            
            # --- Add to gallery ---
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            self.add_thumbnail(pil_img)


    def on_closing(self):
        self.root.destroy()


    def add_thumbnail(self, pil_img):
        idx = len(self.items)
        item = ThumbnailItem(self.scrollable_frame, pil_img, idx, app=self,
                             bg=self.palette['item_bg'])
        item.pack(anchor="nw", fill="x", padx=6, pady=3)
        self.items.append(item)

    # Selection logic
    def on_item_click(self, item, ctrl=False, shift=False):
        # ctrl toggles, shift selects range from last_selected_index
        if shift and self.last_selected_index is not None:
            start = min(self.last_selected_index, item.index)
            end = max(self.last_selected_index, item.index)
            self.clear_selection(keep_ui=True)
            for i in range(start, end+1):
                if i < len(self.items):
                    self.select_item(self.items[i], add=True, update_last=False)
            self.last_selected_index = item.index
            return

        if ctrl:
            # toggle
            if item in self.selected:
                self.unselect_item(item)
            else:
                self.select_item(item, add=True)
            self.last_selected_index = item.index
            return

        # plain click = single selection
        self.clear_selection(keep_ui=True)
        self.select_item(item, add=False)
        self.last_selected_index = item.index

    def select_item(self, item, add=False, update_last=True):
        if not add:
            # clear others
            self.clear_selection(keep_ui=True)
        if item not in self.selected:
            self.selected.add(item)
            item.selected = True
            item.var.set(True)
            item.configure_highlight()
        if update_last:
            self.last_selected_index = item.index

    def unselect_item(self, item):
        if item in self.selected:
            self.selected.remove(item)
        item.selected = False
        item.var.set(False)
        item.configure_highlight()

    def clear_selection(self, keep_ui=False):
        # keep_ui=True -> just unselect logically but don't clear UI? We'll clear UI as well.
        for it in list(self.selected):
            it.selected = False
            it.var.set(False)
            it.configure_highlight()
        self.selected.clear()
        self.last_selected_index = None

    def select_all(self):
        for it in self.items:
            self.select_item(it, add=True)



###############################################################################################################################################################################
    def open_editor(self):
        """
        Enhanced editor function using lite_image_editor.py functionality
        
        Input: self.selected - set of selected items with img_ref attribute
        Output: Updates item.img_ref with edited image and refreshes thumbnail
        """
        
        if not self.selected:
            messagebox.showwarning("Editor", "Please select an image to edit.")
            return

        item = list(self.selected)[0]
        orig = item.img_ref.copy().convert("RGB")
        history = [orig.copy()]
        hist_idx = [0]  # Mutable container for history index
        
        win = tk.Toplevel(self.root)
        win.title("Lite Image Editor")
        win.attributes("-fullscreen", True)
        win.bind("<Escape>", lambda e: win.attributes("-fullscreen", False))
        win.bind("<F11>", lambda e: win.attributes("-fullscreen", True))
        win.config(bg="#1a1a1a")
        
        global running_or_passing
        running_or_passing = True
        
        # Variables for adjustments
        bright_var = tk.DoubleVar(value=1.0)
        contrast_var = tk.DoubleVar(value=1.0)
        sat_var = tk.DoubleVar(value=1.0)
        
        # Top bar
        top = tk.Frame(win, bg="#2d2d2d", height=40)
        top.pack(fill="x")
        tk.Label(top, text="Image Editor", font=("Arial", 12, "bold"),
                bg="#2d2d2d", fg="#fff").pack(side="left", padx=10)
        tk.Label(top, text="F11: Fullscreen | Esc: Exit Fullscreen | + - Scroll to Zoom",
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
                
        def enable_fullscreen(retries=5):
            if retries == 0:
                return
            win.attributes("-fullscreen", True)
            if not win.attributes("-fullscreen"):
                win.after(200, lambda: enable_fullscreen(retries-1))

        win.after_idle(enable_fullscreen)
        win.transient(self.root)
        win.focus_force()
        win.grab_set() 
        
        
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
        
        def apply_filter(ftype):
            if ftype is None:
                result = orig.copy()

            elif ftype == 'gray':
                result = ImageOps.grayscale(orig).convert("RGB")

            elif ftype == 'sepia':
                gray = ImageOps.grayscale(orig)
                result = ImageOps.colorize(gray, "#704214", "#C0A080").convert("RGB")

            elif ftype == 'vintage':
                gray = ImageOps.grayscale(orig)
                tmp = ImageOps.colorize(gray, "#704214", "#C0A080")
                result = ImageEnhance.Contrast(tmp).enhance(0.9).convert("RGB")

            elif ftype == 'invert':
                result = ImageOps.invert(orig.convert("RGB"))

            elif ftype in ('red', 'green', 'blue'):
                r, g, b = orig.convert("RGB").split()

                if ftype == 'red':
                    result = Image.merge("RGB", (r, r, r))
                elif ftype == 'green':
                    result = Image.merge("RGB", (g, g, g))
                else:  # blue
                    result = Image.merge("RGB", (b, b, b))

            else:
                return  # safety

            add_to_history(result)
            reset_sliders()
            show_preview()
            status.config(text=f"Applied: {ftype or 'original'}")

        # Filter definitions with icon keys and names
        filters = [
            ('original', "Original", lambda: apply_filter(None)),
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
        
        # Center - Preview
        center = tk.Frame(main, bg="#1a1a1a")
        center.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        canvas = tk.Canvas(center, bg="#1a1a1a", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        zoom_level = [1.0]
        pan_start = [0, 0]
        canvas_img = [None]
        tk_preview = [None]

        
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
            history[:] = history[:hist_idx[0] + 1]
            history.append(img.copy())

            if len(history) > 5:
                history.pop(0)
            else:
                hist_idx[0] += 1

            hist_idx[0] = len(history) - 1

        
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
            reset_zoom()
        
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
            current = get_current_image()
            item.img_ref = current.copy()
            item.update_thumbnail()
            item.configure_highlight()
            win.destroy()
            global running_or_passing
            running_or_passing = False
            self.update_frame()
            
            messagebox.showinfo("Editor", "Saved edits to thumbnail.")
        
        def cancel_editer():
            win.destroy()
            global running_or_passing
            running_or_passing = False
            self.update_frame()
        
        tk.Button(bottom, text="⟲ Undo", command=undo, bg="#4a4a4a",
                 fg="#fff", width=8).pack(side="left", padx=5, pady=2)
        
        tk.Button(bottom, text="Save Changes", command=save_and_close,
                 bg="#2f79f6", fg="white", padx=20, pady=2,
                 font=("Arial", 10, "bold")).pack(side="right", padx=5)
        tk.Button(bottom, text="Cancel", command=cancel_editer,
                 bg="#c94a3f", fg="white", padx=20, pady=2,
                 font=("Arial", 10, "bold")).pack(side="right", padx=5)
        
        # Initial preview
        show_preview()


###############################################################################################################################################################################
    # --- Save / Delete Functions ---
    def save_selected(self):
        if not self.selected:
            messagebox.showinfo("Save", "No images selected.")
            return

        # Ensure folder exists to save images automatically
        save_folder = self.settings_data['image_location']
        
        # Get parameter from command line
        if len(sys.argv) > 1:
            id_for_img_add = sys.argv[1]
            #(f"Received parameter: {id_for_img_add}")
        else:
            messagebox.showwarning("Warning", "No parameter provided for image update.")
            id_for_img_add = None

        if not os.path.exists(save_folder):
            os.makedirs(save_folder)

        # Save all selected images
        for item in list(self.selected):
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"img_{timestamp}.{self.settings_data['image_format']}"
            filepath = os.path.join(save_folder, filename)
            db_path = f"{save_folder}/{filename}"

            # Update database if ID is provided
            if id_for_img_add:
                self.conn = sqlite3.connect('dbs/patient_hospital.db')
                self.cursor = self.conn.cursor()
                self.cursor.execute(
                    """UPDATE patient_full_details
                       SET Image = Image || ? WHERE id = ?;""",
                    ("," + db_path, id_for_img_add)
                )
                self.conn.commit()
                self.conn.close()

            # Save image file
            item.img_ref.save(filepath)

        messagebox.showinfo("Save", f"{len(self.selected)} image(s) saved to '{save_folder}'")


    def delete_selected(self):
        if not self.selected:
            messagebox.showinfo("Delete", "No images selected.")
            return

        global running_or_passing
        running_or_passing = True

        selected_items = list(self.selected)
        self.clear_selection()

        to_delete = sorted([it.index for it in selected_items], reverse=True)

        for idx in to_delete:
            if idx < len(self.items):
                it = self.items[idx]

                # Clear references
                it.img_ref = None
                it.thumb_tk = None
                it.destroy()
                del self.items[idx]

        # Reindex safely
        for i, it in enumerate(self.items):
            it.index = i

        self.last_selected_index = None

        messagebox.showinfo("Delete", "Deleted selected item(s).")

        import gc
        gc.collect()

        running_or_passing = False
        self.update_frame()


    def od_function(self):
        self.flage_od_os = "OD"

    def os_function(self):
        self.flage_od_os = "OS"

    def on_close(self):
        self.camera_running = False
        try:
            if getattr(self, "cap", None) and self.cap.isOpened():
                self.cap.release()
        finally:
            try:
                GPIO.cleanup()
            except:
                ...
            self.root.destroy()


def create_camera_widget(parent):
    """
    Creates and embeds the camera app inside a parent frame.
    Works like an 'iframe' version for embedding in other Tkinter UIs.
    """
    app = CameraApp(parent)
    return app

if __name__ == "__main__":
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    app = CameraApp(root)
    root.mainloop()
