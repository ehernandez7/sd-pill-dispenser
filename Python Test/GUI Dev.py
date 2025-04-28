"""
pill_box_v2_fixed.py
————————
GUI pill-box with 14 slots • LED/Audio alarm • stepper motor
+ Settings → Debug  (tests LED / Audio / manual slot select)
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

import schedule, threading, os, time
from datetime import datetime, timedelta

# ───────── optional hardware ─────────
try:
    from gpiozero import LED, DigitalOutputDevice, MotionSensor
    led = LED(14)                       # BCM 14
    pir = MotionSensor(4)
    DIR_PIN, STEP_PIN = 21, 20          # BCM pins
    dir_pin  = DigitalOutputDevice(DIR_PIN)
    step_pin = DigitalOutputDevice(STEP_PIN)
    HW = True
except Exception:
    led = None; pir = None; HW = False

try:
    import pygame
    pygame.mixer.init()
    ALARM_FILE = "Python Test/Good place.mp3"            # put an MP3/WAV here
except Exception:
    pygame = None

# ───────── 14-slot pattern (sum = 200 steps) ─────────
STEPS_PER_SLOT = [14,14,14,15,15,14,14,14,14,14,15,15,14,14]
current_slot   = 0   # 0 = Sunday-Morning

def move_steps(n, forward=True, delay=0.002):
    """Pulse STEP pin n times."""
    if not HW:
        print(f"[sim] {n} steps {'fwd' if forward else 'rev'}")
        time.sleep(n * delay * 2)
        return
    dir_pin.value = 1 if forward else 0
    for _ in range(n):
        step_pin.on(); time.sleep(delay)
        step_pin.off(); time.sleep(delay)

def rotate_to_slot(target:int):
    """Rotate forward to reach target slot (0-13)."""
    global current_slot
    diff = (target - current_slot) % 14
    for i in range(diff):
        seg = (current_slot + i) % 14
        move_steps(STEPS_PER_SLOT[seg], True)
    current_slot = target
    print("[motor] at slot", current_slot)

def reset_motor():
    rotate_to_slot(0)

# ── add global jog flag ─────────────────────────────────────────────
_jog_event = threading.Event()   # cleared => stop

def _jog_motor(forward: bool):
    """Spin continuously until _jog_event is cleared."""
    while not _jog_event.is_set():
        move_steps(1, forward, delay=0.002)   # 1 step at a time, ~500 Hz max


# ───────── LED / audio helpers ─────────
def audio_on():
    if pygame and os.path.exists(ALARM_FILE):
        pygame.mixer.music.load(ALARM_FILE)
        pygame.mixer.music.play(-1)

def audio_off():
    if pygame and pygame.mixer.get_init():
        pygame.mixer.music.stop()

# ───────── alarm trigger ─────────
days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

def trigger_alarm(day, disp_time, period):
    slot = days.index(day) * 2 + (0 if period == "Morning" else 1)
    threading.Thread(target=rotate_to_slot, args=(slot,), daemon=True).start()
    Clock.schedule_once(lambda dt: AlarmPopup(day, disp_time).open(), 0)

# ───────── Alarm popup ─────────
class AlarmPopup(Popup):
    def __init__(self, day, when, **kw):
        kw.setdefault("auto_dismiss", False)
        super().__init__(**kw)
        self.title      = "⏰  Medicine Reminder  ⏰"
        self.size_hint  = (.8, .5)
        self.flash_on   = False

        # layout
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            self.bg = Color(.05, .05, .20, 1)
            self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        self.msg = Label(text=f"[b]Time to take your medicine[/b]\n{day}  {when}",
                         markup=True, font_size="20sp",
                         halign="center", color=(1,1,1,1))
        root.add_widget(self.msg)

        row = BoxLayout(size_hint=(1,.3), spacing=10)
        snooze = Button(text="Snooze 5 min", font_size="18sp")
        stop   = Button(text="Stop",        font_size="18sp")
        snooze.bind(on_press=self._snooze)
        stop  .bind(on_press=self._stop)
        row.add_widget(snooze)
        row.add_widget(stop)
        root.add_widget(row)

        self.content = root

        # start flashing & hardware
        self.ev = Clock.schedule_interval(self._flash, 0.7)
        self._start_hardware()

        if pir:
            pir.when_motion = self._pir_stop

    # drawing helpers
    def _upd_rect(self, inst, val):
        self.rect.size = inst.size
        self.rect.pos  = inst.pos

    def _flash(self, _dt):
        self.flash_on = not self.flash_on
        self.bg.rgba  = (.12,.12,.32,1) if self.flash_on else (.05,.05,.20,1)
        self.msg.opacity = 0.6 if self.flash_on else 1
        if led:
            led.on() if self.flash_on else led.off()

    def _start_hardware(self):
        if led: led.on()
        audio_on()

    def _stop_hardware(self):
        if led: led.off()
        audio_off()

    # button callbacks
    def _snooze(self, *_):
        nxt = datetime.now() + timedelta(minutes=5)
        schedule.every().day.at(nxt.strftime("%H:%M")).do(
            trigger_alarm,
            nxt.strftime("%A"),
            nxt.strftime("%I:%M %p"),
            "Evening" if nxt.hour >= 12 else "Morning"
        )
        self._stop()

    def _stop(self, *_):
        if self.ev.is_triggered:
            self.ev.cancel()
        self._stop_hardware()
        if pir:
            pir.when_motion = None          # disarm PIR callback
        self.dismiss()

    # ---- NEW helper called by PIR ----
    def _pir_stop(self):
        # run in the Kivy thread
        Clock.schedule_once(lambda dt: self._stop())

# ───────── Home screen ─────────
class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.day_idx = 0

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(.05,.05,.20,1)
            self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        root.add_widget(Label(text="Pill Container Scheduler",
                              font_size="24sp", color=(1,1,1,1), size_hint=(1,.15)))

        self.clock = Label(font_size="18sp", color=(1,1,1,1), size_hint=(1,.1))
        root.add_widget(self.clock)
        Clock.schedule_interval(lambda dt: self._update_clock(), 1)

        # day nav
        nav = BoxLayout(size_hint=(1,.15))
        left = Button(text="<", background_color=(.2,.4,.8,1))
        right= Button(text=">", background_color=(.2,.4,.8,1))
        left .bind(on_press=lambda *_: self._change_day(-1))
        right.bind(on_press=lambda *_: self._change_day( 1))
        self.day_lab = Label(text=days[self.day_idx], font_size="20sp", color=(1,1,1,1))
        nav.add_widget(left); nav.add_widget(self.day_lab); nav.add_widget(right)
        root.add_widget(nav)

        # morning / evening buttons
        tod = BoxLayout(size_hint=(1,.2), spacing=10)
        for period in ("Morning", "Evening"):
            tod.add_widget(Button(text=period,
                                  background_color=(.1,.6,.8,1),
                                  on_press=lambda inst,p=period:self._goto_time(p)))
        root.add_widget(tod)

        # bottom row
        row = BoxLayout(size_hint=(1,.15), spacing=10)
        row.add_widget(Button(text="Test Alarm",
                              background_color=(.3,.7,.9,1),
                              on_press=lambda *_:
                                  trigger_alarm(self.day_lab.text,
                                                datetime.now().strftime("%I:%M %p"),
                                                "Evening" if datetime.now().hour>=12 else "Morning")))
        row.add_widget(Button(text="Reset Motor",
                              background_color=(.3,.5,.9,1),
                              on_press=lambda *_:
                                  threading.Thread(target=reset_motor, daemon=True).start()))
        row.add_widget(Button(text="Settings",
                              background_color=(.2,.5,.7,1),
                              on_press=lambda *_: setattr(self.manager,"current","settings")))
        root.add_widget(row)

        self.add_widget(root)

    def _upd_rect(self, inst, val):
        self.rect.size = inst.size
        self.rect.pos  = inst.pos

    def _update_clock(self):
        self.clock.text = datetime.now().strftime("%I:%M:%S %p")

    def _change_day(self, delta):
        self.day_idx = (self.day_idx + delta) % 7
        self.day_lab.text = days[self.day_idx]

    def _goto_time(self, period):
        ts = self.manager.get_screen("time")
        ts.set_day_period(self.day_lab.text, period)
        self.manager.current = "time"

# ───────── Time picker screen ─────────
class TimeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.day = self.period = ""

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(.05,.05,.20,1)
            self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        self.info = Label(font_size="20sp", color=(1,1,1,1), size_hint=(1,.15))
        root.add_widget(self.info)

        # time pick grid
        grid = GridLayout(cols=3, spacing=10, size_hint=(1,.4))
        self.h  = Label(text="08", font_size="24sp", color=(1,1,1,1))
        self.m  = Label(text="00", font_size="24sp", color=(1,1,1,1))
        self.ap = Label(text="AM", font_size="24sp", color=(1,1,1,1))

        arrows = [("▲", self._ch_h,  1),
                  ("▲", self._ch_m,  1),
                  ("▲", self._ch_ap, 1),
                  ("▼", self._ch_h, -1),
                  ("▼", self._ch_m, -1),
                  ("▼", self._ch_ap,-1)]
        for idx, (sym, fn, step) in enumerate(arrows):
            btn = Button(text=sym, font_size="24sp", background_color=(.2,.4,.8,1))
            btn.bind(on_press=lambda inst,f=fn,s=step: f(s))
            grid.add_widget(btn)
            if idx == 2:
                grid.add_widget(self.h); grid.add_widget(self.m); grid.add_widget(self.ap)
        root.add_widget(grid)

        # nav
        nav = BoxLayout(size_hint=(1,.15), spacing=10)
        nav.add_widget(Button(text="Back", background_color=(.2,.4,.8,1),
                              on_press=lambda *_: setattr(self.manager,"current","home")))
        nav.add_widget(Button(text="OK",   background_color=(.3,.7,.9,1),
                              on_press=self._save))
        root.add_widget(nav)

        self.add_widget(root)

    def _upd_rect(self, inst, val):
        self.rect.size = inst.size
        self.rect.pos  = inst.pos

    def set_day_period(self, day, period):
        self.day, self.period = day, period
        self.info.text = f"{day} — {period}"

    @staticmethod
    def _wrap(val, inc, mod):
        return (val + inc) % mod

    def _ch_h(self, step):
        new = self._wrap(int(self.h.text)-1, step, 12) + 1
        self.h.text = f"{new:02}"

    def _ch_m(self, step):
        new = self._wrap(int(self.m.text), step, 60)
        self.m.text = f"{new:02}"

    def _ch_ap(self, _step):
        self.ap.text = "PM" if self.ap.text == "AM" else "AM"

    def _save(self, *_):
        hr_12 = int(self.h.text)
        hr_24 = hr_12 % 12 + (12 if self.ap.text == "PM" else 0)
        t24   = f"{hr_24:02}:{self.m.text}"
        disp  = f"{self.h.text}:{self.m.text} {self.ap.text}"
        getattr(schedule.every(), self.day.lower()).at(t24).do(
            trigger_alarm, self.day, disp, self.period
        )
        self.manager.current = "home"

# ───────── Debug screens ─────────
class DebugScreen(Screen):
    """LED / Audio tests, and entry to SlotPicker."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.prev_slot = None

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(.05,.05,.20,1); self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        root.add_widget(Label(text="Debug Menu", font_size="24sp", color=(1,1,1,1)))

        # LED row
        led_row = BoxLayout(size_hint=(1,.15), spacing=10)
        led_row.add_widget(Button(text="LED ON",  background_color=(.0,.6,.2,1),
                                  on_press=lambda *_: (led.on() if led else None)))
        led_row.add_widget(Button(text="LED OFF", background_color=(.6,.1,.1,1),
                                  on_press=lambda *_: (led.off() if led else None)))
        root.add_widget(led_row)

        # audio row
        aud_row = BoxLayout(size_hint=(1,.15), spacing=10)
        aud_row.add_widget(Button(text="Audio ON",  background_color=(.1,.6,.8,1),
                                  on_press=lambda *_: audio_on()))
        aud_row.add_widget(Button(text="Audio OFF", background_color=(.6,.1,.3,1),
                                  on_press=lambda *_: audio_off()))
        root.add_widget(aud_row)

        # slot select
        root.add_widget(Button(text="Manual Slot Select",
                               background_color=(.3,.7,.9,1), size_hint=(1,.15),
                               on_press=lambda *_: setattr(self.manager,"current","slots")))
        
        # motor jog
        jog_box = BoxLayout(size_hint=(1,.15), spacing=10)
        left_btn  = Button(text="◀ Hold", background_color=(.4,.4,.9,1))
        right_btn = Button(text="Hold ▶", background_color=(.4,.4,.9,1))

        # start jog on press, stop on release
        left_btn.bind(
            on_press = lambda *_: self._start_jog(False),
            on_release = lambda *_: self._stop_jog()
        )
        right_btn.bind(
            on_press = lambda *_: self._start_jog(True),
            on_release = lambda *_: self._stop_jog()
        )
        jog_box.add_widget(left_btn)
        jog_box.add_widget(right_btn)
        root.add_widget(jog_box)


        # back
        root.add_widget(Button(text="Back", background_color=(.2,.4,.8,1), size_hint=(1,.15),
                               on_press=lambda *_: self._leave()))
        self.add_widget(root)
    
    # ── motor jog helpers ───────────────────────────────────────────
    def _start_jog(self, forward: bool):
        _jog_event.clear()
        threading.Thread(target=_jog_motor, args=(forward,), daemon=True).start()

    def _stop_jog(self):
        _jog_event.set()


    def _upd_rect(self, inst, val):
        self.rect.size = inst.size
        self.rect.pos  = inst.pos

    def on_pre_enter(self):
        self.prev_slot = current_slot

    def _leave(self):
        if self.prev_slot is not None and self.prev_slot != current_slot:
            threading.Thread(target=rotate_to_slot,
                             args=(self.prev_slot,), daemon=True).start()
        self.manager.current = "home"

class SlotPickerScreen(Screen):
    """Buttons 0-13 → rotate to that slot."""
    def __init__(self, **kw):
        super().__init__(**kw)
        root = GridLayout(cols=4, padding=10, spacing=10)
        with root.canvas.before:
            Color(.05,.05,.20,1); self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        for i in range(14):
            root.add_widget(Button(text=str(i),
                                   background_color=(.3,.7,.9,1),
                                   on_press=lambda inst,slot=i:
                                       threading.Thread(target=rotate_to_slot,
                                                        args=(slot,), daemon=True).start()))
        root.add_widget(Button(text="Back", background_color=(.2,.4,.8,1),
                               on_press=lambda *_: setattr(self.manager,"current","debug")))
        self.add_widget(root)

    def _upd_rect(self, inst, val):
        self.rect.size = inst.size
        self.rect.pos  = inst.pos

# ───────── Settings screen ─────────
class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(.05,.05,.20,1); self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        root.add_widget(Label(text="Settings", font_size="24sp", color=(1,1,1,1)))
        root.add_widget(Button(text="Sync Pi RTC",
                               background_color=(.3,.7,.9,1),
                               on_press=lambda *_: os.system("sudo timedatectl set-ntp true")))
        root.add_widget(Button(text="Debug",
                               background_color=(.6,.5,.1,1),
                               on_press=lambda *_: setattr(self.manager,"current","debug")))
        root.add_widget(Button(text="Back",
                               background_color=(.2,.4,.8,1),
                               on_press=lambda *_: setattr(self.manager,"current","home")))
        self.add_widget(root)

    def _upd_rect(self, inst, val):
        self.rect.size = inst.size
        self.rect.pos  = inst.pos

# ───────── App wrapper ─────────
class PillSchedulerApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(TimeScreen(name="time"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(DebugScreen(name="debug"))
        sm.add_widget(SlotPickerScreen(name="slots"))
        return sm

    def on_start(self):
        threading.Thread(target=self._sched_loop, daemon=True).start()

    @staticmethod
    def _sched_loop():
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    PillSchedulerApp().run()
