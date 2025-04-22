from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

import schedule
import threading
from datetime import datetime, timedelta
import os

days_of_week = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


# ───────── Alarm popup with slow flashing ─────────
class AlarmPopup(Popup):
    def __init__(self, day, time_str, **kwargs):
        super().__init__(**kwargs)
        self.title = "⏰  Medicine Reminder  ⏰"
        self.size_hint = (0.8, 0.5)
        self.flash_interval = 0.7
        self.flash_state = False

        # --- layout ---
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            self.bg_color = Color(0.05, 0.05, 0.20, 1)
            self.bg_rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._update_rect, pos=self._update_rect)

        self.msg = Label(
            text=f"[b]Time to take your medicine[/b]\n{day}  {time_str}",
            markup=True,
            font_size="20sp",
            halign="center",
            color=(1, 1, 1, 1),
        )
        root.add_widget(self.msg)

        btn_row = BoxLayout(size_hint=(1, 0.3), spacing=10)
        snooze = Button(text="Snooze 5 min", font_size="18sp")
        stop   = Button(text="Stop",        font_size="18sp")
        snooze.bind(on_press=self._snooze)
        stop.bind(on_press=self._stop)
        btn_row.add_widget(snooze)
        btn_row.add_widget(stop)
        root.add_widget(btn_row)

        self.content = root
        self._flash_ev = Clock.schedule_interval(self._flash, self.flash_interval)
        self.open()

    # ---------- helpers ----------
    def _update_rect(self, inst, val):
        self.bg_rect.size = inst.size
        self.bg_rect.pos  = inst.pos

    def _flash(self, dt):
        self.flash_state = not self.flash_state
        if self.flash_state:
            self.bg_color.rgba = (0.12, 0.12, 0.32, 1)
            self.msg.opacity   = 0.6
        else:
            self.bg_color.rgba = (0.05, 0.05, 0.20, 1)
            self.msg.opacity   = 1

    def _snooze(self, *_):
        new_dt   = datetime.now() + timedelta(minutes=5)
        day_name = new_dt.strftime("%A")
        t24      = new_dt.strftime("%H:%M")
        display  = new_dt.strftime("%I:%M %p")
        schedule.every().day.at(t24).do(trigger_alarm, day_name, display)
        self._stop()

    def _stop(self, *_):
        if self._flash_ev.is_triggered:
            self._flash_ev.cancel()
        self.dismiss()


# ——— called from schedule (background) then forwarded to UI thread ———
def trigger_alarm(day, display_time):
    Clock.schedule_once(lambda dt: AlarmPopup(day, display_time), 0)


# ——— background scheduler loop ———
def run_scheduler():
    while True:
        schedule.run_pending()
        threading.Event().wait(1)


# ───────── Screens ─────────
class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.day_idx = 0

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(0.05, 0.05, 0.20, 1)
            self.bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        root.add_widget(Label(text="Pill Container Scheduler",
                              font_size="24sp", color=(1,1,1,1),
                              size_hint=(1, 0.15)))

        self.clock = Label(text="", font_size="18sp", color=(1,1,1,1),
                           size_hint=(1, 0.1))
        root.add_widget(self.clock)
        Clock.schedule_interval(lambda dt: self._tick(), 1)

        # day navigator
        nav = BoxLayout(size_hint=(1, 0.15))
        left  = Button(text="<", font_size="20sp",
                       background_color=(0.2,0.4,0.8,1))
        right = Button(text=">", font_size="20sp",
                       background_color=(0.2,0.4,0.8,1))
        left .bind(on_press=lambda *_: self._change_day(-1))
        right.bind(on_press=lambda *_: self._change_day(+1))
        nav.add_widget(left)
        self.day_lbl = Label(text=days_of_week[self.day_idx],
                             font_size="20sp", color=(1,1,1,1))
        nav.add_widget(self.day_lbl)
        nav.add_widget(right)
        root.add_widget(nav)

        # Morning / Afternoon / Evening
        tod = BoxLayout(size_hint=(1, 0.2), spacing=10)
        for name in ("Morning", "Afternoon", "Evening"):
            btn = Button(text=name, font_size="18sp",
                         background_color=(0.1,0.6,0.8,1))
            btn.bind(on_press=lambda inst, n=name: self._goto_time(n))
            tod.add_widget(btn)
        root.add_widget(tod)

        # Test Alarm + Settings
        row = BoxLayout(size_hint=(1, 0.15), spacing=10)
        test = Button(text="Test Alarm",
                      background_color=(0.3,0.7,0.9,1))
        test.bind(on_press=lambda *_:
                  trigger_alarm(self.day_lbl.text,
                                datetime.now().strftime("%I:%M %p")))
        row.add_widget(test)

        sett = Button(text="Settings",
                      background_color=(0.2,0.5,0.7,1))
        sett.bind(on_press=lambda *_:
                  setattr(self.manager, "current", "settings"))
        row.add_widget(sett)
        root.add_widget(row)

        self.add_widget(root)

    # ---------- internals ----------
    def _upd_rect(self, inst, val):
        self.bg.size = inst.size
        self.bg.pos  = inst.pos

    def _tick(self):
        self.clock.text = datetime.now().strftime("%I:%M:%S %p")

    def _change_day(self, step):
        self.day_idx = (self.day_idx + step) % 7
        self.day_lbl.text = days_of_week[self.day_idx]

    def _goto_time(self, tod):
        scr = self.manager.get_screen("time")
        scr.set_day_time(self.day_lbl.text, tod)
        self.manager.current = "time"


class TimeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.day, self.tod = "", ""

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(0.05, 0.05, 0.20, 1)
            self.bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        self.info = Label(text="", font_size="20sp", color=(1,1,1,1),
                          size_hint=(1, 0.15))
        root.add_widget(self.info)

        # grid arrows + labels
        grid = GridLayout(cols=3, spacing=10, size_hint=(1, 0.4))

        self.h  = Label(text="12", font_size="24sp", color=(1,1,1,1))
        self.m  = Label(text="00", font_size="24sp", color=(1,1,1,1))
        self.ap = Label(text="AM", font_size="24sp", color=(1,1,1,1))

        arrows = [("▲", self._ch_h,  1),
                  ("▲", self._ch_m,  1),
                  ("▲", self._ch_ap, 1),
                  ("▼", self._ch_h, -1),
                  ("▼", self._ch_m, -1),
                  ("▼", self._ch_ap, -1)]

        for idx, (sym, fn, step) in enumerate(arrows):
            btn = Button(text=sym, font_size="24sp",
                         background_color=(0.2,0.4,0.8,1))
            btn.bind(on_press=lambda inst, f=fn, s=step: f(s))
            grid.add_widget(btn)
            if idx == 2:                   # after first three ↑ buttons
                grid.add_widget(self.h)
                grid.add_widget(self.m)
                grid.add_widget(self.ap)

        root.add_widget(grid)

        nav = BoxLayout(size_hint=(1, 0.15), spacing=10)
        back = Button(text="Back",
                      background_color=(0.2,0.4,0.8,1))
        back.bind(on_press=lambda *_:
                  setattr(self.manager, "current", "home"))
        ok   = Button(text="OK",
                      background_color=(0.3,0.7,0.9,1))
        ok.bind(on_press=self._confirm)
        nav.add_widget(back)
        nav.add_widget(ok)
        root.add_widget(nav)

        self.add_widget(root)

    # ---------- helpers ----------
    def _upd_rect(self, inst, val):
        self.bg.size = inst.size
        self.bg.pos  = inst.pos

    def set_day_time(self, day, tod):
        self.day, self.tod = day, tod
        self.info.text = f"{day} — {tod}"

    def _ch_h(self, step):
        h = (int(self.h.text) - 1 + step) % 12 + 1
        self.h.text = f"{h:02}"

    def _ch_m(self, step):
        m = (int(self.m.text) + step) % 60
        self.m.text = f"{m:02}"

    def _ch_ap(self, _):
        self.ap.text = "PM" if self.ap.text == "AM" else "AM"

    def _confirm(self, *_):
        # convert to 24‑hour for schedule lib
        hour12 = int(self.h.text)
        hour24 = hour12 % 12
        if self.ap.text == "PM":
            hour24 += 12
        t24     = f"{hour24:02}:{self.m.text}"
        display = f"{self.h.text}:{self.m.text} {self.ap.text}"

        getattr(schedule.every(), self.day.lower()).at(t24).do(
            trigger_alarm, self.day, display
        )
        setattr(self.manager, "current", "home")


class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(0.05, 0.05, 0.20, 1)
            self.bg = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        root.add_widget(Label(text="Settings", font_size="24sp",
                              color=(1,1,1,1)))

        sync = Button(text="Sync Pi RTC",
                      background_color=(0.3,0.7,0.9,1))
        sync.bind(on_press=lambda *_:
                  os.system("sudo timedatectl set-ntp true"))
        root.add_widget(sync)

        back = Button(text="Back",
                      background_color=(0.2,0.4,0.8,1))
        back.bind(on_press=lambda *_:
                  setattr(self.manager, "current", "home"))
        root.add_widget(back)

        self.add_widget(root)

    def _upd_rect(self, inst, val):
        self.bg.size = inst.size
        self.bg.pos  = inst.pos


# ───────── App wrapper ─────────
class PillSchedulerApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(TimeScreen(name="time"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

    def on_start(self):
        threading.Thread(target=run_scheduler, daemon=True).start()


if __name__ == "__main__":
    PillSchedulerApp().run()
