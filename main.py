import os
import sys
import re
import json
import hashlib
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import requests
from io import BytesIO
from thefuzz import fuzz, process
from typing import Dict, Optional
from ttkbootstrap import Style

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ACORN'))
from acorn import create_multi_xci

static_dir = os.path.dirname(os.path.abspath(__file__))
script_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

NSZ_PATTERN = re.compile(r"(?P<name>.*)\[(?:(?P<titleid>[A-Za-z0-9]{16}).*|\[(?P<region>[A-Z]{2})\].*|\[v(?P<version>\d{1,})\].*){2}(?:\.nsz|\.nsp)")

class FileManager:
    def __init__(self, game_manager=None, image_manager=None) -> None:
        self.files: Dict[str, Dict] = {}
        self.choices: Dict[str, str] = {}
        self.titles_db_path = os.path.join(script_dir, "titledb", "titles.json")
        self.titles_db_url = "https://tinfoil.media/repo/db/titles.json"
        self.load_count = 0
        self.chunk_size = 100
        self.game_manager = game_manager
        self.image_manager = image_manager

        os.makedirs(os.path.dirname(self.titles_db_path), exist_ok=True)

    def load_data(self, filepath: str) -> None:
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as file:
                    self.files = json.load(file)
                    self.load_count = 0
                    self.populate_treeview()
                    self.update_choices()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading data: {e}")

    def update_choices(self) -> None:
        for key, file_data in self.files.items():
            if file_data.get('id') and file_data.get('name'):
                self.choices[key] = f"{file_data['name']} {file_data['id']}"

    def sort_files_by_rank(self) -> None:
        sorted_keys = sorted(self.files, key=lambda x: self.files[x].get('rank', 999999))
        self.files = {key: self.files[key] for key in sorted_keys}

    def type_check(self, check_digit: str) -> str:
        type_mapping = {"000": "base", "800": "update"}
        return type_mapping.get(check_digit, "dlc")

    def download_titles_db(self) -> bool:
        try:
            response = requests.get(self.titles_db_url)
            response.raise_for_status()
            with open(self.titles_db_path, 'wb') as file:
                file.write(response.content)
            return True
        except requests.RequestException as e:
            print(f"Failed to download titles.json: {e}")
            return False

    def scan_files(self, directory, pattern):
        scanned_files = []
        stack = [directory]
        while stack:
            current_dir = stack.pop()
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False) and pattern.search(entry.name):
                        scanned_files.append(entry.path)
        return scanned_files

    def refresh_files_thread(self, directory: str) -> None:
        thread = threading.Thread(target=self._refresh_files, args=(directory,))
        thread.start()

    def _refresh_files(self, directory: str) -> None:
        self.game_manager.progress_bar.config(mode='indeterminate')
        self.game_manager.progress_bar.start(10)
        self.files.clear()
        self.choices.clear()

        titles_db_available = os.path.exists(self.titles_db_path) or self.download_titles_db()
        scanned_files = self.scan_files(directory, NSZ_PATTERN)

        for filename in scanned_files:
            match = NSZ_PATTERN.search(os.path.basename(filename))
            titleid = match.group('titleid')
            if titleid:
                file_type = self.type_check(titleid[-3:])
                key = f"{int(titleid, 16)-0x1000:0{16}X}"[:-3] if file_type == 'dlc' else titleid[:-3]
                if key not in self.files:
                    self.files[key] = {
                        'name': match.group('name').strip() or None,
                        'id': titleid,
                        'region': match.group('region') or None,
                        'size': None,
                        'base': [],
                        'update': [],
                        'dlc': [],
                        'intro': None,
                        'iconUrl': None,
                    }
                self.files[key][file_type].append(filename)
                self.choices[key] = f"{match.group('name')} {titleid}"

        if titles_db_available:
            try:
                with open(self.titles_db_path, "r") as file:
                    data = json.load(file)
                    for title in data:
                        title_data = data[title]
                        if title_data['id']:
                            key = title_data['id'][:-3]
                            if self.type_check(title_data['id'][-3:]) == "base" and key in self.files:
                                self.choices[key] = f"{title_data['name']} {title_data['id']}"
                                del title_data['description']
                                del title_data['regions']
                                self.files[key].update(title_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error reading titles database: {e}")

        self.sort_files_by_rank()
        
        try:
            with open(os.path.join(script_dir, "result.json"), 'w') as fp:
                json.dump(self.files, fp)
            self.load_count = 0
            self.populate_treeview()
        except IOError as e:
            print(f"Error saving data: {e}")
        finally:
            self.game_manager.progress_var.set(0)
            self.game_manager.progress_bar.config(mode='determinate')
            self.game_manager.progress_bar.stop()

    def populate_treeview(self) -> None:
        self.clear_treeview()
        self.load_more_items()

    def load_more_items(self) -> None:
        count = 0
        keys = list(self.files.keys())[self.load_count:self.load_count + self.chunk_size]
        for key in keys:
            self.game_manager.treeview.insert("", tk.END, text=self.files[key]['name'] or '', values=(self.files[key]['id'], self.files[key]['region'] or ''))
            count += 1
        self.load_count += count
    
    def clear_treeview(self) -> None:
        self.game_manager.treeview.delete(*self.game_manager.treeview.get_children())

    def refresh(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.refresh_files_thread(directory)

class ImageManager:
    def __init__(self, game_manager=None, file_manager=None) -> None:
        self.image_queue: queue.Queue = queue.Queue()
        self.stop_event: threading.Event = threading.Event()
        self.current_item: Optional[str] = None
        self.cache_dir: str = os.path.join(script_dir, "image_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.default_image_path: str = os.path.join(static_dir, "images", "no_image.png")
        self.transparent_image_path: str = os.path.join(static_dir, "images", "loading.png")
        self.game_manager = game_manager
        self.file_manager = file_manager

    def fetch_image_data(self, url: str, item: str, label: ttk.Label) -> None:
        try:
            if self.stop_event.is_set():
                return

            if url and "http" in url:
                filename = hashlib.md5(url.encode()).hexdigest() + '.png'
                filepath = os.path.join(self.cache_dir, filename)
            else:
                filepath = self.default_image_path

            if "http" in str(url) and not os.path.isfile(filepath):
                response = requests.get(url)
                response.raise_for_status()
                with Image.open(BytesIO(response.content)) as img:
                    img.thumbnail((200, 200), Image.LANCZOS)
                    img.save(filepath)

            if not os.path.isfile(filepath):
                filepath = self.default_image_path

            with Image.open(filepath) as img:
                img.thumbnail((200, 200), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                if not self.stop_event.is_set() and item == self.current_item:
                    self.image_queue.put(photo)

        except requests.HTTPError as e:
            print(f"HTTP error occurred: {e}")
            self.load_default_image(item, self.default_image_path)
        except Exception as e:
            print(f"Error processing image: {e}")
            self.load_default_image(item, self.default_image_path)

    def load_default_image(self, item: str, img_path: str) -> None:
        if not self.stop_event.is_set() and item == self.current_item:
            with Image.open(img_path) as img:
                img.thumbnail((200, 200), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.image_queue.put(photo)

    def check_queue(self, label: ttk.Label) -> None:
        try:
            photo = self.image_queue.get_nowait()
            label.config(image=photo)
            label.image = photo
        except queue.Empty:
            pass
        label.after(100, self.check_queue, label)

    def start_fetch_thread(self, url: str, item: str, label: ttk.Label) -> None:
        if item == self.current_item:
            return
        self.stop_event.set()
        with self.image_queue.mutex:
            self.image_queue.queue.clear()
        self.stop_event.clear()
        self.current_item = item
        self.load_default_image(item, self.transparent_image_path)
        threading.Thread(target=self.fetch_image_data, args=(url, item, label)).start()

class GameManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.file_manager = FileManager(game_manager=self)
        self.image_manager = ImageManager(game_manager=self)
        self.file_manager.image_manager = self.image_manager
        self.setup_ui()
        self.file_manager.load_data(os.path.join(script_dir, "result.json"))
        self.image_manager.check_queue(self.image_label)
        self.transfer_in_progress = False
        self.process = None
        self.current_filename = None
        self.output_dir = None

    def setup_ui(self) -> None:
        self.root.geometry("800x600")
        self.root.eval('tk::PlaceWindow . center')
        self.root.resizable(False, False)
        self.root.title("EmuRomManager")

        icon_path = os.path.join(script_dir, "switch.ico")
        if os.path.exists(icon_path):
            try:
                # Try .ico format (works on Windows)
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                # Fallback for Linux/Mac - use PNG with iconphoto
                try:
                    icon_img = Image.open(icon_path)
                    icon_photo = ImageTk.PhotoImage(icon_img)
                    self.root.iconphoto(True, icon_photo)
                except Exception as e:
                    print(f"Could not load icon: {e}")

        self.root.eval("tk::PlaceWindow . center")
        style = Style('darkly')

        style.configure("Treeview", rowheight=45, font=('Helvetica', 11))
        style.configure("TButton", font=("Helvetica", 12))
        style.configure("Treeview.Heading", background="#263D55", font=('Helvetica', 11))
        style.configure("Vertical.Progressbar", troughcolor='red', background='green', thickness=30)
        style.configure('Custom.Horizontal.TProgressbar',
                background='#3fff8f',
                troughcolor='#2f2f2f',
                thickness=20,
                troughrelief='sunken',
                borderwidth=2,
                relief='raised')

        self.query = tk.StringVar(value='Search...')

        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=0)
        self.root.grid_rowconfigure(3, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=1)

        self.input_frame = ttk.Frame(master=self.root)
        self.input_frame.grid(row=0, column=0, padx=(10, 15), pady=(10, 0), columnspan=3, sticky='new')
        self.input_frame.grid_rowconfigure(0, weight=1)
        self.input_frame.grid_columnconfigure(0, weight=0)
        self.input_frame.grid_columnconfigure(1, weight=1)
        self.input_frame.grid_columnconfigure(2, weight=1)

        self.select_input_dir = ttk.Button(master=self.input_frame, text="Select Input Folder", command=self.file_manager.refresh)
        self.select_input_dir.grid(row=0, column=0, sticky='w', padx=5)
        self.select_output_dir = ttk.Button(master=self.input_frame, text="Select Output Folder", command=self.set_output_dir)
        self.select_output_dir.grid(row=0, column=1, sticky='w', padx=5)

        self.search_field = ttk.Entry(master=self.input_frame, textvariable=self.query, font=("Helvetica", 12))
        self.search_field.grid(row=0, column=2, sticky='ew')
        self.search_field.bind('<KeyRelease>', self.search)
        self.search_field.bind('<FocusIn>', self.on_entry_click)
        self.search_field.bind('<FocusOut>', self.on_focusout)
        self.search_field.config(foreground='grey')

        self.tree_frame = ttk.Frame(master=self.root, padding=(10, 5))
        self.tree_frame.grid(row=1, column=0, columnspan=3, sticky='new', padx=5, pady=5)
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        self.treeview = self.create_treeview(self.tree_frame)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(master=self.tree_frame, style='Custom.Horizontal.TProgressbar', variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=1, column=0, columnspan=2, padx=0, pady=(10,0), sticky="new")

        self.game_frame = ttk.Frame(master=self.root, height=200)
        self.game_frame.grid(row=2, column=0, columnspan=3, padx=14, pady=0, sticky='new')
        self.game_frame.grid_propagate(False)
        self.game_frame.grid_rowconfigure(0, weight=1)
        self.game_frame.grid_columnconfigure(0, weight=0)
        self.game_frame.grid_columnconfigure(1, weight=1)

        self.image_label = ttk.Label(master=self.game_frame, width=200)
        self.image_label.grid(row=0, column=0, sticky='new')
        self.image_label.grid_propagate(False)

        self.desc_frame = ttk.Frame(master=self.game_frame, padding=(10, 5))
        self.desc_frame.grid(row=0, column=1, padx=0, pady=0, sticky='new')
        self.desc_frame.grid_rowconfigure(0, weight=0)
        self.desc_frame.grid_rowconfigure(1, weight=0)
        self.desc_frame.grid_rowconfigure(2, weight=0)
        self.desc_frame.grid_columnconfigure(0, weight=0)
        self.desc_frame.grid_columnconfigure(1, weight=1)
        
        self.game_name_label = ttk.Label(master=self.desc_frame, text="", font=("Helvetica", 16, "bold"))
        self.game_name_label.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky='nw')

        self.transfer_button = ttk.Button(master=self.desc_frame, text="Transfer Game", state=tk.DISABLED)
        self.transfer_button.grid(row=1, column=0, padx=5, pady=5, sticky='nw')

        self.cancel_button = ttk.Button(master=self.desc_frame, text="Cancel Transfer", state=tk.DISABLED, command=self.cancel_transfer)
        self.cancel_button.grid(row=1, column=1, padx=5, pady=5, sticky='nw')

        self.game_intro_label = ttk.Label(master=self.desc_frame, text="Intro", font=("Helvetica", 12), wraplength=540)
        self.game_intro_label.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='nw')

        self.transfer_frame = ttk.Frame(master=self.root, padding=(10, 5))
        self.transfer_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        self.transfer_frame.grid_propagate(False)
        self.transfer_frame.grid_rowconfigure(0, weight=1)
        self.transfer_frame.grid_columnconfigure(0, weight=1)

        self.output_text = tk.Text(master=self.transfer_frame, bg="#2e2e2e", fg="#ffffff", insertbackground="white")
        self.output_text.grid(row=0, column=0, sticky="nsew")

    def create_treeview(self, frame: tk.Frame) -> ttk.Treeview:
        treeview = ttk.Treeview(master=frame, columns=("titleid", "region"), selectmode='browse', height=4)
        treeview.heading("#0", text="Game", anchor="w")
        treeview.column("#0", stretch=tk.YES, minwidth=300, width=485)
        treeview.heading("titleid", text="TitleID", anchor="w")
        treeview.column("titleid", stretch=tk.YES, minwidth=100, width=150)
        treeview.heading("region", text="Region", anchor="w")
        treeview.column("region", stretch=tk.YES, minwidth=100, width=100)
        treeview.grid(row=0, column=0, sticky='nsew')
        vscroll = ttk.Scrollbar(master=frame, orient="vertical", command=treeview.yview)
        treeview.configure(yscrollcommand=vscroll.set)
        vscroll.grid(row=0, column=1, sticky='ns')
        treeview.bind('<Button-1>', self.on_row_click)
        treeview.bind('<MouseWheel>', self.on_treeview_scroll)
        vscroll.bind('<ButtonRelease-1>', self.on_treeview_scroll)
        treeview.bind('<KeyPress>', self.on_treeview_scroll)
        return treeview
    
    def on_treeview_scroll(self, event: tk.Event) -> None:
        if self.treeview.yview()[1] > 0.99:
            self.file_manager.load_more_items()

    def search(self, event: tk.Event) -> None:
        self.file_manager.load_count = 0
        self.treeview.yview_moveto(0)
        if not self.search_field.get():
            self.file_manager.populate_treeview()
            return
        self.file_manager.clear_treeview()
        results = process.extract(self.search_field.get(), self.file_manager.choices, limit=100, scorer=fuzz.partial_token_sort_ratio)
        for result in results:
            id = result[2]
            self.treeview.insert("", tk.END, text=self.file_manager.files[id]['name'], values=(self.file_manager.files[id]['id'], self.file_manager.files[id]['region']))

    def on_row_click(self, event: tk.Event) -> None:
        if self.transfer_in_progress:
            return
        global current_game
        row_id = event.widget.identify_row(event.y)
        if row_id:
            item = event.widget.item(row_id, 'values')
            key = item[0][:-3]

            current_game = self.file_manager.files[key]

            self.game_name_label.config(text=current_game['name'])
            self.game_intro_label.config(text=current_game['intro'] or "")
            
            self.enable_transfer_button()

            icon_url = current_game.get('iconUrl', os.path.join(script_dir, "images", "no.jpg"))
            self.image_manager.start_fetch_thread(icon_url, row_id, self.image_label)

    def update_transfer_ui(self, text: Optional[str] = None, progress: Optional[int] = None, info: Optional[str] = None, filename: Optional[str] = None) -> None:
        if text:
            self.output_text.insert(tk.END, text)
            self.output_text.see(tk.END)
            self.root.update_idletasks()  # Force immediate GUI update for real-time output
        if progress is not None:
            self.progress_var.set(progress)
            self.root.update_idletasks()  # Force immediate progress update

    def start_process(self, game: Dict) -> None:
        self.transfer_in_progress = True
        if not self.output_dir:
            self.update_transfer_ui(text=f"Output directory is not set.\n")
            return
        self.current_game_files = game['base'] + game['update'] + game['dlc']
        self.output_text.delete('1.0', tk.END)
        self.progress_var.set(0)
        self.disable_transfer_button()
        self.enable_cancel_button()
        threading.Thread(target=self.decompress_and_create_xci).start()

    def decompress_and_create_xci(self) -> None:
        try:
            self.update_transfer_ui(text="Starting XCI creation with ACORN...\n")
            
            result = create_multi_xci(
                files=self.current_game_files,
                output_folder=self.output_dir,
                text_file=None,
                buffer_size=65536,
                progress_callback=lambda msg: self.update_transfer_ui(text=msg)
            )
            
            if result == 0:
                self.update_transfer_ui(text="XCI creation completed successfully!\n")
                self.progress_var.set(100)
            else:
                self.update_transfer_ui(text="XCI creation failed.\n")
                
        except Exception as e:
            self.update_transfer_ui(text=f"An error occurred: {e}\n")
            self.delete_output_files()
        finally:
            self.progress_var.set(0)
            self.progress_bar.stop()
            self.enable_transfer_button()
            self.disable_cancel_button()
            self.transfer_in_progress = False

    def cancel_transfer(self) -> None:
        if self.transfer_in_progress:
            self.update_transfer_ui(text="Transfer canceled by user.\n")
            self.delete_output_files()
            self.transfer_in_progress = False
            self.progress_var.set(0)
            self.progress_bar.stop()
            self.enable_transfer_button()
            self.disable_cancel_button()

    def delete_output_files(self) -> None:
        if self.current_filename:
            file_path = os.path.join(self.output_dir, self.current_filename)
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        self.update_transfer_ui(text=f"Deleted file: {file_path}\n")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.update_transfer_ui(text=f"Retrying to delete file: {file_path}. Attempt {attempt + 1}\n")
                        time.sleep(1)
                    else:
                        self.update_transfer_ui(text=f"Error deleting file {file_path}: {e}\n")
        else:
            self.update_transfer_ui(text="No file to delete\n")

    def disable_transfer_button(self) -> None:
        self.transfer_button.bind('<Button-1>', lambda e: None)
        self.transfer_button.config(state=tk.DISABLED)

    def enable_transfer_button(self) -> None:
        self.transfer_button.bind('<Button-1>', lambda e: self.start_process(current_game))
        self.transfer_button.config(state=tk.NORMAL)

    def set_output_dir(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir = directory
            self.enable_transfer_button()

    def on_entry_click(self, event: tk.Event) -> None:
        if self.search_field.get() == 'Search...':
            self.search_field.delete(0, "end")
            self.search_field.insert(0, '')
            self.search_field.config(foreground='white')

    def on_focusout(self, event: tk.Event) -> None:
        if self.search_field.get() == '':
            self.search_field.insert(0, 'Search...')
            self.search_field.config(foreground='grey')

    def disable_cancel_button(self) -> None:
        self.cancel_button.config(state=tk.DISABLED)

    def enable_cancel_button(self) -> None:
        self.cancel_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = GameManager(root)
    root.mainloop()
