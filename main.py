import os
# Set dummy video driver BEFORE pygame import to prevent SDL window creation
# that interferes with tkinter window manager
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import csv
import sys
import json
import ctypes
from ctypes import wintypes
import pyperclip
import pygame
import pyautogui
import logging
import time

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'app.log')
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

CONFIG_FILE = "config.json"
route_list = []
current_index = 0
progress_file = None
input_mode = "clipboard"
config_data = {}
all_joysticks = {}

class BindingDetector:
    """Handles combination input detection (chords)."""
    def __init__(self):
        self.pressed = set()
        self.committed_chord = None  # Stores the chord when all inputs released
        self.is_listening = False
        self.field = None
        
    def start(self, field):
        self.is_listening = True
        self.field = field
        self.pressed.clear()
        self.committed_chord = None
        logging.info(f"[BIND] Started listening for {field}")
        
    def stop(self):
        self.is_listening = False
        self.field = None
        self.pressed.clear()
        self.committed_chord = None
            
    def add_input(self, input_id):
        """Add an input to the current chord."""
        if not self.is_listening:
            return False
            
        self.pressed.add(input_id)
        logging.info(f"[BIND] Added input: {input_id}, current chord: {self.pressed}")
        return True
        
    def remove_input(self, input_id):
        """Remove an input (on release). Track max chord seen."""
        if not self.is_listening:
            return
            
        if input_id in self.pressed:
            # Capture chord BEFORE removing (includes input being removed)
            current_chord = self.get_capture()
            
            self.pressed.discard(input_id)
            logging.info(f"[BIND] Removed input: {input_id}, remaining: {self.pressed}")
            
            # Update committed_chord to the largest chord seen
            if current_chord is not None:
                if self.committed_chord is None:
                    self.committed_chord = current_chord
                else:
                    # Compare by length (number of inputs in chord)
                    current_len = 1 if not isinstance(current_chord, tuple) else len(current_chord)
                    committed_len = 1 if not isinstance(self.committed_chord, tuple) else len(self.committed_chord)
                    if current_len >= committed_len:
                        self.committed_chord = current_chord
                        logging.info(f"[BIND] Updated committed chord: {current_chord}")
            
    def get_capture(self):
        """Get the captured chord. Returns the committed chord or current pressed inputs."""
        if self.committed_chord is not None:
            return self.committed_chord
            
        if not self.pressed:
            return None
            
        # Sort for consistent comparison
        inputs = sorted(self.pressed, key=lambda x: str(x))
        
        if len(inputs) == 1:
            return inputs[0]
        else:
            return tuple(inputs)
            
    def has_inputs(self):
        return len(self.pressed) > 0

detector = BindingDetector()

def ensure_single_instance():
    """Prevent multiple instances using Windows named mutex."""
    mutex_name = "Global\\EDNA_SingleInstance_Mutex"
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        return False
    return True

def save_config(cfg):
    global config_data
    try:
        config_path = os.path.join(log_dir, CONFIG_FILE)
        with open(config_path, "w") as f:
            json.dump(cfg, f)
        config_data.update(cfg)
        logging.info("[CONFIG] Saved")
    except Exception as e:
        logging.error(f"[CONFIG] Error: {e}")

def load_config():
    global config_data
    cfg = {
        "next_btn": None,
        "prev_btn": None,
        "enter_key": None,
        "mode": "clipboard"
    }
    config_path = os.path.join(log_dir, CONFIG_FILE)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                loaded = json.load(f)
                cfg.update(loaded)
        except Exception as e:
            logging.error(f"[CONFIG] Load error: {e}")
    config_data = cfg
    return cfg

def save_progress(path, idx):
    try:
        with open(os.path.join(routes_dir, path), "w") as f:
            json.dump({"current_index": idx}, f)
    except Exception as e:
        logging.error(f"[PROGRESS] Error: {e}")

def load_progress(path):
    file_path = os.path.join(routes_dir, path)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return int(data.get("current_index", 0))
        except Exception as e:
            logging.error(f"[PROGRESS] Error: {e}")
    return 0

routes_dir = os.path.join(log_dir, "Routes")

def ensure_routes_dir():
    if not os.path.exists(routes_dir):
        os.makedirs(routes_dir)
        logging.info(f"[ROUTES] Created Routes folder: {routes_dir}")

def list_csv_files():
    ensure_routes_dir()
    if not os.path.exists(routes_dir):
        return []
    return sorted([f for f in os.listdir(routes_dir) if f.lower().endswith('.csv')])

def load_route(csv_file):
    full_path = os.path.join(routes_dir, csv_file)
    loaded = []
    with open(full_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            loaded.append({
                "System": row["System Name"].strip(),
                "ArrivalDist": float(row.get("Distance To Arrival", 0) or 0),
                "RemainingDist": float(row.get("Distance Remaining", 0) or 0),
                "Neutron": row.get("Neutron Star", "").strip(),
                "Jumps": int(row.get("Jumps", 0) or 0)
            })
    return loaded

# Global reference to tkinter root for window management
tk_root = None

def perform_action(system_name):
    global input_mode, tk_root
    lower_name = system_name.lower()
    logging.info(f"[ACTION] {lower_name} (mode={input_mode})")
    if input_mode == "clipboard":
        pyperclip.copy(lower_name)
    else:
        # Send keystrokes directly - Elite Dangerous should have focus
        # since the user pressed a joystick button while playing
        # Type in lowercase with normal human-like delay (110ms between keys)
        pyautogui.typewrite(lower_name, interval=0.11)
        time.sleep(0.18)
        pyautogui.press('return')
        logging.info(f"[ACTION] Typed: {lower_name}")

def setup_joystick():
    global all_joysticks
    pygame.init()
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    logging.info(f"[JOYSTICK] count={count}")
    all_joysticks = {}
    for i in range(count):
        js = pygame.joystick.Joystick(i)
        js.init()
        iid = js.get_instance_id()
        all_joysticks[iid] = js
        logging.info(f"[JOYSTICK] [{i}] {js.get_name()} instance_id={iid} ({js.get_numbuttons()} buttons)")
    return count > 0

def format_binding(val):
    """Convert stored binding to human-readable string."""
    if val is None:
        return "Not bound"
    if isinstance(val, str):
        return f"Keyboard: {val}"
    if isinstance(val, (list, tuple)):
        if len(val) == 2 and isinstance(val[1], int):
            # Single joystick button: (instance_id, button)
            iid, btn = val
            js = all_joysticks.get(iid)
            name = js.get_name() if js else f"Device {iid}"
            return f"{name}: btn {btn}"
        else:
            # Combination
            parts = []
            for item in val:
                if isinstance(item, str):
                    parts.append(f"Key:{item}")
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    iid, btn = item
                    js = all_joysticks.get(iid)
                    name = js.get_name() if js else f"Dev{iid}"
                    parts.append(f"{name}:{btn}")
            return " + ".join(parts)
    return str(val)

def bindings_equal(stored, current):
    """Check if stored binding matches current input."""
    if stored is None:
        return False
    if isinstance(stored, str):
        return stored == current
    if isinstance(stored, (list, tuple)):
        stored_tuple = tuple(stored)
        if isinstance(current, (list, tuple)):
            current_tuple = tuple(current)
        else:
            current_tuple = (current,)
        return stored_tuple == current_tuple
    return stored == current

def build_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    global tk_root
    root = tk.Tk()
    tk_root = root
    root.title("EDNA")
    root.geometry("900x600")
    root.resizable(True, True)
    
    # Set window icon
    try:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EDNA_Icon.png")
        icon_img = tk.PhotoImage(file=icon_path)
        root.iconphoto(True, icon_img)
    except Exception as e:
        logging.warning(f"[GUI] Could not load icon: {e}")

    # Elite Dangerous color scheme
    ELITE_ORANGE = '#FF7700'
    ELITE_AMBER = '#FFB900'
    ELITE_GREEN = '#00FF44'
    ELITE_CRIMSON = '#FF0033'
    ELITE_DARK = '#0A0D14'
    
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TButton', background=ELITE_ORANGE, foreground=ELITE_DARK, font=('Segoe UI', 10))
    style.configure('TFrame', background=ELITE_DARK)
    style.configure('TNotebook', background=ELITE_DARK)
    style.configure('TNotebook.Tab', background=ELITE_DARK, foreground=ELITE_AMBER, padding=[10, 2])
    style.map('TNotebook.Tab', background=[('selected', ELITE_ORANGE)], foreground=[('selected', ELITE_DARK)])
    style.configure('TLabel', background=ELITE_DARK, foreground=ELITE_AMBER)
    style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), foreground=ELITE_ORANGE, background=ELITE_DARK)
    style.configure('Subtitle.TLabel', font=('Segoe UI', 9), foreground=ELITE_AMBER, background=ELITE_DARK)
    style.configure('TEntry', fieldbackground=ELITE_DARK, foreground=ELITE_AMBER)
    style.configure('TCombobox', fieldbackground=ELITE_DARK, foreground=ELITE_AMBER)
    
    root.configure(bg=ELITE_DARK)

    tabs = ttk.Notebook(root)
    tabs.pack(fill='both', expand=True, padx=10, pady=10)

    # --- MAIN TAB ---
    tab_main = ttk.Frame(tabs)
    tabs.add(tab_main, text='MAIN')
    
    # Navigation row: << PREVIOUS | [System Name] | NEXT >>
    nav_frame = ttk.Frame(tab_main)
    nav_frame.pack(pady=(20, 5))
    
    def btn_prev():
        global current_index
        if current_index > 0:
            current_index -= 1
            save_progress(progress_file, current_index)
            update_gui()
    
    def btn_next():
        global current_index
        if current_index < len(route_list) - 1:
            current_index += 1
            save_progress(progress_file, current_index)
            update_gui()
    
    def btn_reset():
        global current_index
        if messagebox.askyesno("Reset Route", "Reset to the beginning of the route?"):
            current_index = 0
            save_progress(progress_file, current_index)
            update_gui()
    
    btn_prev_widget = tk.Button(nav_frame, text='<< PREVIOUS', bg=ELITE_ORANGE, fg=ELITE_DARK, 
                                 font=('Segoe UI', 10, 'bold'), command=btn_prev,
                                 activebackground='#FF9944', activeforeground=ELITE_DARK,
                                 relief='flat', padx=15, pady=5)
    btn_prev_widget.pack(side='left', padx=5)
    
    lbl_sys = tk.Label(nav_frame, text='---', font=('Segoe UI', 24, 'bold'), 
                        fg=ELITE_AMBER, bg=ELITE_DARK, width=25)
    lbl_sys.pack(side='left', padx=10)
    
    btn_next_widget = tk.Button(nav_frame, text='NEXT >>', bg=ELITE_ORANGE, fg=ELITE_DARK,
                                 font=('Segoe UI', 10, 'bold'), command=btn_next,
                                 activebackground='#FF9944', activeforeground=ELITE_DARK,
                                 relief='flat', padx=15, pady=5)
    btn_next_widget.pack(side='left', padx=5)
    
    # Info row: Distance Left | Neutron Jumps Remaining
    info_frame = ttk.Frame(tab_main)
    info_frame.pack(pady=(10, 5))
    
    lbl_dist = tk.Label(info_frame, text='Distance Left: 0 ly', font=('Segoe UI', 11),
                         fg=ELITE_AMBER, bg=ELITE_DARK)
    lbl_dist.pack(side='left', padx=20)
    
    lbl_neutron = tk.Label(info_frame, text='Neutron Jumps: 0', font=('Segoe UI', 11),
                            fg=ELITE_GREEN, bg=ELITE_DARK)
    lbl_neutron.pack(side='left', padx=20)
    
    # Reset button centered below
    reset_frame = ttk.Frame(tab_main)
    reset_frame.pack(pady=(15, 5))
    btn_reset_widget = tk.Button(reset_frame, text='Reset Route', bg=ELITE_CRIMSON, fg='#FFFFFF',
                                  font=('Segoe UI', 10, 'bold'), command=btn_reset,
                                  activebackground='#FF4466', activeforeground='#FFFFFF',
                                  relief='flat', padx=20, pady=5)
    btn_reset_widget.pack()

    # --- LOAD TAB ---
    tab_load = ttk.Frame(tabs)
    tabs.add(tab_load, text='LOAD')
    ttk.Label(tab_load, text='Select Route', style='Title.TLabel').pack(pady=10)
    lb_csv = tk.Listbox(tab_load, bg=ELITE_DARK, fg=ELITE_AMBER, font=('Segoe UI', 10),
                        selectbackground=ELITE_ORANGE, selectforeground=ELITE_DARK)
    lb_csv.pack(fill='both', expand=True, padx=20, pady=10)
    for f in list_csv_files():
        lb_csv.insert(tk.END, f)

    def on_load(event):
        sel = lb_csv.curselection()
        if sel:
            fname = lb_csv.get(sel[0])
            logging.info(f"[GUI] loading: {fname}")
            global route_list, current_index, progress_file
            route_list.clear()
            route_list.extend(load_route(fname))
            current_index = 0
            progress_file = f"progress_{os.path.splitext(os.path.basename(fname))[0]}.json"
            messagebox.showinfo("Loaded", f"'{fname}' loaded with {len(route_list)} jumps")

    lb_csv.bind('<<ListboxSelect>>', on_load)

    # --- SETTINGS TAB ---
    tab_set = ttk.Frame(tabs)
    tabs.add(tab_set, text='SETTINGS')
    ttk.Label(tab_set, text='Bindings', style='Title.TLabel').pack(pady=(10, 5))

    mode_var = tk.StringVar(value=config_data.get("mode", "clipboard"))
    ttk.Label(tab_set, text='Input Mode:').pack()
    mode_cb = ttk.Combobox(tab_set, textvariable=mode_var, values=['clipboard', 'keystroke'], state='readonly', width=30)
    mode_cb.pack(pady=2)
    
    def on_mode_change(*args):
        global input_mode
        input_mode = mode_var.get()
        config_data["mode"] = input_mode
        save_config(config_data)
        logging.info(f"[GUI] mode changed to {input_mode}")
    
    mode_var.trace_add('write', on_mode_change)

    # Binding entries
    binding_entries = {}
    binding_vars = {}

    def add_entry(parent, label_text, field):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=30, pady=4)
        ttk.Label(frame, text=label_text, width=15).pack(side='left')
        ent = ttk.Entry(frame, state='readonly', width=35, background=ELITE_DARK, foreground=ELITE_AMBER)
        ent.pack(side='left', padx=5)
        binding_entries[field] = ent
        var = tk.StringVar()
        binding_vars[field] = var
        ent.config(textvariable=var)
        ttk.Button(frame, text='DETECT', style='TButton',
                   command=lambda f=field: start_detect(f)).pack(side='left')
        return ent

    add_entry(tab_set, 'Next Jump:', 'next_btn')
    add_entry(tab_set, 'Previous Jump:', 'prev_btn')
    add_entry(tab_set, 'Enter Jump:', 'enter_key')

    # Set initial display
    for field in ['next_btn', 'prev_btn', 'enter_key']:
        binding_vars[field].set(format_binding(config_data.get(field)))

    lbl_status = ttk.Label(tab_set, foreground=ELITE_GREEN, background=ELITE_DARK)
    lbl_status.pack(pady=(10, 0))

    def start_detect(field):
        logging.info(f"[GUI] detect clicked for {field}")
        lbl_status.config(text=f'Listening for {field}... press combo then release')
        detector.start(field)

    def finish_detect():
        """Called when inputs are released - captures the chord."""
        if not detector.is_listening:
            return
            
        capture = detector.get_capture()
        if capture:
            field = detector.field
            logging.info(f"[GUI] captured {field} = {capture}")
            config_data[field] = capture
            binding_vars[field].set(format_binding(capture))
            save_config(config_data)
            lbl_status.config(text='Bound!')
            detector.stop()
            # Clear status after 2 seconds
            root.after(2000, lambda: lbl_status.config(text=''))
        else:
            lbl_status.config(text='No input detected')
            detector.stop()

    def clear_detect():
        detector.stop()
        lbl_status.config(text='')

    # Keyboard handling for binding
    pressed_keys = set()
    
    def on_key_down(event):
        if not detector.is_listening:
            return
        key = event.keysym
        # Ignore modifier keys by themselves unless they're part of a combo
        # Track all keys including modifiers
        pressed_keys.add(key)
        detector.add_input(key)
        lbl_status.config(text=f'Listening... pressed: {" + ".join(sorted(pressed_keys))}')
        
    def on_key_up(event):
        if not detector.is_listening:
            return
        key = event.keysym
        if key in pressed_keys:
            pressed_keys.discard(key)
        detector.remove_input(key)
        if detector.has_inputs():
            lbl_status.config(text=f'Listening... pressed: {" + ".join(sorted(pressed_keys))}')
        else:
            # All keys released - capture the chord
            finish_detect()

    root.bind('<KeyPress>', on_key_down)
    root.bind('<KeyRelease>', on_key_up)

    # --- EVENT LOOP ---
    prev_button_states = {}  # (instance_id, btn) -> state
    processed_events = set()  # Prevent duplicate processing in same frame
    gameplay_pressed = set()  # Track currently pressed buttons in normal mode
    combo_triggered = set()   # Track which combos have been triggered this hold
    
    def check_bindings():
        """Check if current gameplay_pressed matches any binding."""
        global current_index
        nonlocal gameplay_pressed, combo_triggered
        
        nb = config_data.get("next_btn")
        pb = config_data.get("prev_btn")
        ek = config_data.get("enter_key")
        
        # Check each binding against currently pressed set
        for binding, action_name, action_fn in [
            (nb, "NEXT", lambda: current_index < len(route_list) - 1 and current_index + 1),
            (pb, "PREV", lambda: current_index > 0 and current_index - 1),
            (ek, "ENTER", lambda: True)
        ]:
            if binding is None:
                continue
                
            # Convert binding to a set for comparison
            if isinstance(binding, (list, tuple)):
                if len(binding) == 2 and isinstance(binding[1], int):
                    # Single button: (iid, btn)
                    binding_set = {tuple(binding)}
                else:
                    # Combination: tuple of inputs
                    binding_set = set(tuple(x) if isinstance(x, list) else x for x in binding)
            else:
                # Single string key
                binding_set = {binding}
            
            # Check if binding is fully satisfied by currently pressed inputs
            if binding_set.issubset(gameplay_pressed):
                # Check if we already triggered this exact combo
                binding_key = str(sorted(binding_set, key=str))
                if binding_key not in combo_triggered:
                    combo_triggered.add(binding_key)
                    
                    if action_name == "NEXT":
                        idx = action_fn()
                        if idx is not False:
                            current_index = idx
                            save_progress(progress_file, current_index)
                            logging.info(f"[INPUT] NEXT -> {route_list[current_index]['System']}")
                    elif action_name == "PREV":
                        idx = action_fn()
                        if idx is not False:
                            current_index = idx
                            save_progress(progress_file, current_index)
                            logging.info(f"[INPUT] PREV -> {route_list[current_index]['System']}")
                    elif action_name == "ENTER":
                        if input_mode != "clipboard":
                            perform_action(route_list[current_index]["System"])
    
    def event_loop():
        global current_index
        
        processed_events.clear()
        events = pygame.event.get()
        
        # Process pygame events first
        for ev in events:
            if ev.type == pygame.JOYBUTTONDOWN:
                iid = ev.instance_id
                btn = ev.button
                input_id = (iid, btn)
                processed_events.add(input_id)
                
                if detector.is_listening:
                    detector.add_input(input_id)
                    js = all_joysticks.get(iid)
                    name = js.get_name() if js else f"Dev{iid}"
                    remaining = []
                    for item in detector.pressed:
                        if isinstance(item, tuple) and len(item) == 2:
                            js2 = all_joysticks.get(item[0])
                            n2 = js2.get_name() if js2 else f"Dev{item[0]}"
                            remaining.append(f"{n2}:{item[1]}")
                        else:
                            remaining.append(str(item))
                    lbl_status.config(text=f'Listening... pressed: {" + ".join(remaining)}')
                else:
                    # Normal mode - track pressed buttons
                    gameplay_pressed.add(input_id)
                    check_bindings()
                        
            elif ev.type == pygame.JOYBUTTONUP:
                iid = ev.instance_id
                btn = ev.button
                input_id = (iid, btn)
                processed_events.add(input_id)
                
                if detector.is_listening:
                    detector.remove_input(input_id)
                    if not detector.has_inputs():
                        # All buttons released - capture
                        finish_detect()
                    else:
                        # Show remaining pressed inputs
                        remaining = []
                        for item in detector.pressed:
                            if isinstance(item, tuple) and len(item) == 2:
                                js2 = all_joysticks.get(item[0])
                                n2 = js2.get_name() if js2 else f"Dev{item[0]}"
                                remaining.append(f"{n2}:{item[1]}")
                            else:
                                remaining.append(str(item))
                        lbl_status.config(text=f'Listening... pressed: {" + ".join(remaining)}')
                else:
                    # Normal mode - remove from pressed set and clear triggers
                    gameplay_pressed.discard(input_id)
                    if not gameplay_pressed:
                        combo_triggered.clear()

        # Poll joystick state for buttons not handled by events
        for iid, js in all_joysticks.items():
            for btn in range(js.get_numbuttons()):
                input_id = (iid, btn)
                
                # Skip if already processed by event
                if input_id in processed_events:
                    continue
                
                is_pressed = js.get_button(btn)
                was_pressed = prev_button_states.get(input_id, False)
                
                if detector.is_listening:
                    if is_pressed and not was_pressed:
                        # Button just pressed (not caught by event)
                        detector.add_input(input_id)
                        remaining = []
                        for item in detector.pressed:
                            if isinstance(item, tuple) and len(item) == 2:
                                js2 = all_joysticks.get(item[0])
                                n2 = js2.get_name() if js2 else f"Dev{item[0]}"
                                remaining.append(f"{n2}:{item[1]}")
                            else:
                                remaining.append(str(item))
                        lbl_status.config(text=f'Listening... pressed: {" + ".join(remaining)}')
                    elif not is_pressed and was_pressed:
                        # Button just released (not caught by event)
                        detector.remove_input(input_id)
                        if not detector.has_inputs():
                            finish_detect()
                else:
                    # Normal mode - poll for buttons not caught by events
                    if is_pressed and not was_pressed:
                        gameplay_pressed.add(input_id)
                        check_bindings()
                    elif not is_pressed and was_pressed:
                        gameplay_pressed.discard(input_id)
                        if not gameplay_pressed:
                            combo_triggered.clear()
                
                prev_button_states[input_id] = is_pressed

        root.after(20, event_loop)

    event_loop()

    # --- GUI UPDATE LOOP ---
    def update_gui():
        try:
            if current_index < len(route_list):
                lbl_sys.config(text=route_list[current_index]["System"])
                
                # RemainingDist is already cumulative (distance from current system to destination)
                remaining_dist = round(route_list[current_index]["RemainingDist"], 2)
                lbl_dist.config(text=f'Distance Left: {remaining_dist:,.2f} Lightyears')
                
                # Count neutron jumps remaining
                neutron_remaining = sum(1 for s in route_list[current_index:] if s.get("Neutron"))
                lbl_neutron.config(text=f'Neutron Jumps Remaining: {neutron_remaining:,}')
            else:
                lbl_sys.config(text='---')
                lbl_dist.config(text='Distance Left: 0 ly')
                lbl_neutron.config(text='Neutron Jumps Remaining: 0')
        except Exception as e:
            logging.error(f"[GUI] update error: {e}")
        root.after(1000, update_gui)

    update_gui()
    root.mainloop()

def main():
    global current_index, route_list, progress_file, config_data, input_mode

    if not ensure_single_instance():
        logging.warning("[MAIN] Another instance is already running. Exiting.")
        sys.exit(0)

    logging.info("=" * 60)
    logging.info("[MAIN] EDNA starting")

    pygame.init()
    pygame.joystick.init()

    load_config()
    input_mode = config_data.get("mode", "clipboard")

    csv_files = list_csv_files()
    if not csv_files:
        logging.error("[MAIN] No CSV files found.")
        sys.exit(1)

    csv_path = csv_files[0]
    route_list = load_route(csv_path)
    progress_file = f"progress_{os.path.splitext(os.path.basename(csv_path))[0]}.json"
    current_index = load_progress(progress_file)
    if current_index >= len(route_list):
        current_index = 0
    logging.info(f"[MAIN] route: {len(route_list)} jumps, index={current_index}")

    setup_joystick()
    build_gui()

if __name__ == "__main__":
    main()
