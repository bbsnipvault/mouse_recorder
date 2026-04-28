# MIT License
# Copyright (c) 2024
#
# Mouse Recorder - Aufnahme und Wiedergabe von Mausbewegungen und Klicks.
# Zwei unabhängige Slots, einstellbare Geschwindigkeit, systemweite Hotkeys.

import tkinter as tk
from tkinter import filedialog
from pynput.mouse import Listener, Controller, Button
import threading
import time
import json
import keyboard


class MouseRecorder:
    """
    Kapselt die Aufnahme- und Wiedergabelogik für einen einzelnen Slot.
    Kann unabhängig von der GUI verwendet werden.
    """

    def __init__(self):
        self.recording = False       # True, solange eine Aufnahme läuft
        self.playing = False         # True, solange eine Wiedergabe läuft
        self.mouse_events = []       # Liste aller aufgezeichneten Events
        self.mouse = Controller()    # pynput-Controller zum Steuern der Maus
        self.speed = 1.0             # Wiedergabefaktor (>1 = schneller)

    def start_stop_recording(self):
        """Schaltet die Aufnahme um: startet sie, wenn sie nicht läuft, stoppt sie sonst."""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Startet die Aufnahme und registriert den pynput-Listener."""
        self.recording = True
        self.mouse_events = []  # Vorherige Aufnahme verwerfen
        self.listener = Listener(on_move=self.on_move, on_click=self.on_click)
        self.listener.start()
        print("Recording started.")

    def stop_recording(self):
        """Stoppt den Listener und beendet die Aufnahme."""
        if self.recording:
            self.listener.stop()
            self.recording = False
            print("Recording stopped.")

    def on_move(self, x, y):
        """Callback: wird von pynput bei jeder Mausbewegung aufgerufen."""
        if self.recording:
            # Event-Format: ('move', (x, y), timestamp)
            self.mouse_events.append(('move', (x, y), time.time()))

    def on_click(self, x, y, button, pressed):
        """Callback: wird von pynput bei Mausklicks aufgerufen."""
        if self.recording:
            event_type = 'press' if pressed else 'release'
            button_type = 'left' if button == Button.left else 'right'
            # Event-Format: ('press'/'release', 'left'/'right', (x, y), timestamp)
            self.mouse_events.append((event_type, button_type, (x, y), time.time()))

    def save_events(self, filename):
        """Speichert alle aufgezeichneten Events als JSON-Datei."""
        with open(filename, 'w') as f:
            json.dump(self.mouse_events, f)
        print(f"Events saved to {filename}")

    def load_events(self, filename):
        """Lädt Events aus einer JSON-Datei in den aktuellen Slot."""
        with open(filename, 'r') as f:
            self.mouse_events = json.load(f)
        print(f"Events loaded from {filename}")

    def play_events(self):
        """
        Spielt alle aufgezeichneten Events sequenziell ab.
        Die Wartezeit zwischen Events wird durch self.speed skaliert.
        Läuft typischerweise in einem eigenen Thread.
        """
        if not self.playing:
            self.playing = True
            # Zeitreferenz: Timestamp des ersten Events
            start_time = self.mouse_events[0][2] if self.mouse_events else 0

            for event in self.mouse_events:
                if not self.playing:
                    break  # Abbruch durch stop_playback()

                event_type, *event_data = event
                event_time = event_data[-1]  # Letztes Element ist immer der Timestamp

                if event_type == 'move':
                    x, y = event_data[0]
                    # Warten bis zum nächsten Event, skaliert mit Geschwindigkeit
                    time.sleep((event_time - start_time) / self.speed)
                    self.mouse.position = (x, y)

                elif event_type in ('press', 'release'):
                    button_type, (x, y) = event_data[0], event_data[1]
                    button = Button.left if button_type == 'left' else Button.right
                    time.sleep((event_time - start_time) / self.speed)
                    if event_type == 'press':
                        self.mouse.press(button)
                    else:
                        self.mouse.release(button)

                # Nächste Wartezeit relativ zum aktuellen Event berechnen
                start_time = event_time

            self.playing = False
            print("Playback finished.")

    def stop_playback(self):
        """Bricht eine laufende Wiedergabe ab. play_events() prüft self.playing in der Schleife."""
        self.playing = False


class MouseRecorderApp:
    """
    GUI-Schicht des Mouse Recorders auf Basis von tkinter.
    Verwaltet zwei unabhängige MouseRecorder-Instanzen und bindet systemweite Hotkeys.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Mouse Recorder")

        # Zwei unabhängige Aufnahme-Slots
        self.recorder1 = MouseRecorder()
        self.recorder2 = MouseRecorder()

        self.create_widgets()
        self.bind_hotkeys()

        # Zeitstempel des letzten ESC-Drucks für Doppeldruck-Erkennung
        self.last_esc_time = 0
        keyboard.on_press_key("esc", self.handle_esc)

    def create_widgets(self):
        """Erstellt alle GUI-Elemente und ordnet sie im Fenster an."""

        # Slot 1: Aufnahme und Wiedergabe
        self.record_button1 = tk.Button(
            self.root,
            text="Start Recording 1  [W+Y]",
            command=self.start_stop_recording1
        )
        self.record_button1.pack(pady=5)

        self.play_button1 = tk.Button(
            self.root,
            text="Play Recording 1  [W+X]",
            command=self.play_events1
        )
        self.play_button1.pack(pady=5)

        # Slot 2: Aufnahme und Wiedergabe
        self.record_button2 = tk.Button(
            self.root,
            text="Start Recording 2  [W+A]",
            command=self.start_stop_recording2
        )
        self.record_button2.pack(pady=5)

        self.play_button2 = tk.Button(
            self.root,
            text="Play Recording 2  [W+S]",
            command=self.play_events2
        )
        self.play_button2.pack(pady=5)

        # Speichern und Laden
        self.save_button = tk.Button(
            self.root,
            text="Save Recording",
            command=self.save_events
        )
        self.save_button.pack(pady=5)

        self.load_button = tk.Button(
            self.root,
            text="Load Recording",
            command=self.load_events
        )
        self.load_button.pack(pady=5)

        # Geschwindigkeitsauswahl per Radiobutton
        self.speed_var = tk.IntVar(value=1)
        self.speed_label = tk.Label(self.root, text="Playback Speed:  [Shift+9 / Shift+0]")
        self.speed_label.pack(pady=5)

        self.speed_radio1 = tk.Radiobutton(
            self.root, text="1x (Original Speed)",
            variable=self.speed_var, value=1, command=self.update_speed
        )
        self.speed_radio1.pack(anchor=tk.W)

        self.speed_radio2 = tk.Radiobutton(
            self.root, text="1.15x (15% faster)",
            variable=self.speed_var, value=2, command=self.update_speed
        )
        self.speed_radio2.pack(anchor=tk.W)

        self.speed_radio3 = tk.Radiobutton(
            self.root, text="1.25x (25% faster)",
            variable=self.speed_var, value=3, command=self.update_speed
        )
        self.speed_radio3.pack(anchor=tk.W)

        # Hinweis auf ESC-Verhalten
        esc_label = tk.Label(self.root, text="Stop / Quit:  [ESC] (doppelt zum Beenden)", fg="gray")
        esc_label.pack(pady=(10, 5))

    def bind_hotkeys(self):
        """
        Registriert systemweite Tastenkombinationen über die keyboard-Bibliothek.
        Die Hotkeys funktionieren auch wenn das Fenster nicht im Vordergrund ist.
        """
        keyboard.add_hotkey('w+y', self.start_stop_recording1)
        keyboard.add_hotkey('w+x', self.play_events1)
        keyboard.add_hotkey('w+a', self.start_stop_recording2)
        keyboard.add_hotkey('w+s', self.play_events2)
        keyboard.add_hotkey('shift+9', self.increase_speed)
        keyboard.add_hotkey('shift+0', self.decrease_speed)

    def update_record_button1(self):
        """Aktualisiert Text und Farbe von Button 1 je nach Aufnahmezustand."""
        if self.recorder1.recording:
            self.record_button1.config(text="Stop Recording 1  [W+Y]", fg="red")
        else:
            self.record_button1.config(text="Start Recording 1  [W+Y]", fg="black")

    def update_record_button2(self):
        """Aktualisiert Text und Farbe von Button 2 je nach Aufnahmezustand."""
        if self.recorder2.recording:
            self.record_button2.config(text="Stop Recording 2  [W+A]", fg="red")
        else:
            self.record_button2.config(text="Start Recording 2  [W+A]", fg="black")

    def start_stop_recording1(self, event=None):
        """Startet oder stoppt Aufnahme 1 und aktualisiert den Button über den GUI-Thread."""
        self.recorder1.start_stop_recording()
        # root.after(0, ...) stellt sicher, dass GUI-Updates immer im Hauptthread erfolgen
        self.root.after(0, self.update_record_button1)

    def play_events1(self, event=None):
        """Startet die Wiedergabe von Slot 1 in einem separaten Thread."""
        if not self.recorder1.playing:
            playback_thread = threading.Thread(target=self.recorder1.play_events)
            playback_thread.start()

    def start_stop_recording2(self, event=None):
        """Startet oder stoppt Aufnahme 2 und aktualisiert den Button über den GUI-Thread."""
        self.recorder2.start_stop_recording()
        self.root.after(0, self.update_record_button2)

    def play_events2(self, event=None):
        """Startet die Wiedergabe von Slot 2 in einem separaten Thread."""
        if not self.recorder2.playing:
            playback_thread = threading.Thread(target=self.recorder2.play_events)
            playback_thread.start()

    def save_events(self):
        """
        Öffnet einen Speicherdialog und schreibt die Events als JSON.
        Slot 1 hat Vorrang; ist er leer, wird Slot 2 gespeichert.
        """
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if filename:
            if self.recorder1.mouse_events:
                self.recorder1.save_events(filename)
            elif self.recorder2.mouse_events:
                self.recorder2.save_events(filename)
            else:
                print("No events recorded yet.")

    def load_events(self):
        """Öffnet einen Dateidialog und lädt die Events in Slot 1."""
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filename:
            self.recorder1.load_events(filename)

    def update_speed(self):
        """Setzt die Wiedergabegeschwindigkeit beider Slots anhand der Radiobutton-Auswahl."""
        speed = self.speed_var.get()
        if speed == 1:
            self.recorder1.speed = 1.0
            self.recorder2.speed = 1.0
        elif speed == 2:
            self.recorder1.speed = 1.15
            self.recorder2.speed = 1.15
        elif speed == 3:
            self.recorder1.speed = 1.25
            self.recorder2.speed = 1.25

    def increase_speed(self):
        """Erhöht die Wiedergabegeschwindigkeit beider Slots um 10 %."""
        self.recorder1.speed *= 1.1
        self.recorder2.speed *= 1.1
        print(f"Speed increased to {self.recorder1.speed:.2f}x")

    def decrease_speed(self):
        """Verringert die Wiedergabegeschwindigkeit beider Slots um 10 %."""
        self.recorder1.speed *= 0.9
        self.recorder2.speed *= 0.9
        print(f"Speed decreased to {self.recorder1.speed:.2f}x")

    def handle_esc(self, event=None):
        """
        ESC-Handler mit Doppeldruck-Erkennung:
        - Einmal ESC: stoppt laufende Aufnahmen und Wiedergaben beider Slots.
        - Zweimal ESC innerhalb von 0,5 Sekunden: beendet das Programm.
        Beide Slots werden unabhängig geprüft (kein elif), damit nie ein Slot übersprungen wird.
        """
        current_time = time.time()

        if current_time - self.last_esc_time < 0.5:
            # Doppeldruck erkannt: Programm beenden
            self.root.quit()
        else:
            # Einfacher Druck: Aufnahmen und Wiedergaben stoppen
            if self.recorder1.recording:
                self.recorder1.stop_recording()
                self.root.after(0, self.update_record_button1)
            if self.recorder1.playing:
                self.recorder1.stop_playback()

            if self.recorder2.recording:
                self.recorder2.stop_recording()
                self.root.after(0, self.update_record_button2)
            if self.recorder2.playing:
                self.recorder2.stop_playback()

        self.last_esc_time = current_time


if __name__ == "__main__":
    root = tk.Tk()
    app = MouseRecorderApp(root)
    root.mainloop()
