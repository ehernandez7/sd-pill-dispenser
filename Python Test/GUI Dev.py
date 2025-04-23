from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

import schedule, threading, os
from datetime import datetime, timedelta
# ── LED setup (optional) ──────────────────────────
try:
    from gpiozero import LED
    led = LED(14)             # BCM pin 14
except Exception:
    led = None                # running off-Pi / no GPIO

# ── Pygame sound setup (optional) ────────────────
try:
    import pygame
    pygame.mixer.init()
    ALARM_FILE = "Python Test/Good place.mp3"  # put an MP3/WAV in same folder
except Exception:
    pygame = None

days_of_week = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]


# ───────── Alarm popup ─────────
class AlarmPopup(Popup):
    def __init__(self, day, t_str, **kw):
        super().__init__(**kw)
        self.title      = "⏰  Medicine Reminder  ⏰"
        self.size_hint  = (0.8, 0.5)
        self.interval   = 0.7   # flash period
        self.flash_on   = False

        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            self.bg_col = Color(0.05, 0.05, 0.20, 1)
            self.bg_rec = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._upd_rect, pos=self._upd_rect)

        self.label = Label(text=f"[b]Time to take your medicine[/b]\n{day}  {t_str}",
                           markup=True, font_size="20sp",
                           halign="center", color=(1,1,1,1))
        root.add_widget(self.label)

        row = BoxLayout(size_hint=(1,0.3), spacing=10)
        snooze = Button(text="Snooze 5 min", font_size="18sp")
        stop   = Button(text="Stop",        font_size="18sp")
        snooze.bind(on_press=self._snooze)
        stop  .bind(on_press=self._stop)
        row.add_widget(snooze); row.add_widget(stop)
        root.add_widget(row)
        self.content = root

        # start UI flash + hardware alarm
        self.flash_ev = Clock.schedule_interval(self._flash, self.interval)
        self._start_hardware()
        self.open()

    # -------------- flashing --------------
    def _upd_rect(self, inst, val):
        self.bg_rec.size = inst.size; self.bg_rec.pos = inst.pos

    def _flash(self, dt):
        self.flash_on = not self.flash_on
        if self.flash_on:
            self.bg_col.rgba = (0.12, 0.12, 0.32, 1)
            self.label.opacity = 0.6
            if led: led.on()
        else:
            self.bg_col.rgba = (0.05, 0.05, 0.20, 1)
            self.label.opacity = 1
            if led: led.off()

    # -------------- hardware --------------
    def _start_hardware(self):
        if pygame and os.path.exists(ALARM_FILE):
            try:
                pygame.mixer.music.load(ALARM_FILE)
                pygame.mixer.music.play(loops=-1)
            except Exception as e:
                print("Audio error:", e)

    def _stop_hardware(self):
        if led: led.off()
        if pygame and pygame.mixer.get_init():
            pygame.mixer.music.stop()

    # -------------- buttons ---------------
    def _snooze(self, *_):
        new_dt  = datetime.now() + timedelta(minutes=5)
        day     = new_dt.strftime("%A")
        t24     = new_dt.strftime("%H:%M")
        disp    = new_dt.strftime("%I:%M %p")
        schedule.every().day.at(t24).do(trigger_alarm, day, disp)
        self._stop()

    def _stop(self, *_):
        if self.flash_ev.is_triggered: self.flash_ev.cancel()
        self._stop_hardware()
        self.dismiss()


# —— function schedule calls —— 
def trigger_alarm(day, disp_time):
    Clock.schedule_once(lambda dt: AlarmPopup(day, disp_time), 0)


# —— scheduler thread —— 
def scheduler_loop():
    while True:
        schedule.run_pending()
        threading.Event().wait(1)


# ───────── GUI screens (unchanged except for imports) ─────────
class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); self.idx = 0
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        with root.canvas.before:
            Color(0.05,0.05,0.20,1); self.bg = Rectangle(size=root.size,pos=root.pos)
        root.bind(size=self._upd,pos=self._upd)
        root.add_widget(Label(text="Pill Container Scheduler",
                              font_size="24sp",color=(1,1,1,1),size_hint=(1,0.15)))
        self.clock = Label(font_size="18sp",color=(1,1,1,1),size_hint=(1,0.1))
        root.add_widget(self.clock); Clock.schedule_interval(lambda dt:self._tick(),1)

        nav = BoxLayout(size_hint=(1,0.15))
        nav.add_widget(Button(text="<",font_size="20sp",background_color=(0.2,0.4,0.8,1),
                              on_press=lambda *_:self._chg(-1)))
        self.day = Label(text=days_of_week[self.idx],font_size="20sp",color=(1,1,1,1))
        nav.add_widget(self.day)
        nav.add_widget(Button(text=">",font_size="20sp",background_color=(0.2,0.4,0.8,1),
                              on_press=lambda *_:self._chg(+1)))
        root.add_widget(nav)

        tod = BoxLayout(size_hint=(1,0.2),spacing=10)
        for name in ("Morning","Afternoon","Evening"):
            tod.add_widget(Button(text=name,font_size="18sp",background_color=(0.1,0.6,0.8,1),
                                  on_press=lambda inst,n=name:self._goto(n)))
        root.add_widget(tod)

        row = BoxLayout(size_hint=(1,0.15),spacing=10)
        row.add_widget(Button(text="Test Alarm",background_color=(0.3,0.7,0.9,1),
                              on_press=lambda *_:trigger_alarm(self.day.text,
                                   datetime.now().strftime("%I:%M %p"))))
        row.add_widget(Button(text="Settings",background_color=(0.2,0.5,0.7,1),
                              on_press=lambda *_:setattr(self.manager,"current","settings")))
        root.add_widget(row)
        self.add_widget(root)

    def _upd(self,i,v): self.bg.size=i.size; self.bg.pos=i.pos
    def _tick(self): self.clock.text=datetime.now().strftime("%I:%M:%S %p")
    def _chg(self,s): self.idx=(self.idx+s)%7; self.day.text=days_of_week[self.idx]
    def _goto(self,tod):
        ts=self.manager.get_screen("time"); ts.set_day_time(self.day.text,tod)
        setattr(self.manager,"current","time")


class TimeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw); self.day=self.tod=""
        root=BoxLayout(orientation="vertical",padding=10,spacing=10)
        with root.canvas.before:
            Color(0.05,0.05,0.20,1); self.bg=Rectangle(size=root.size,pos=root.pos)
        root.bind(size=self._upd,pos=self._upd)
        self.info=Label(font_size="20sp",color=(1,1,1,1),size_hint=(1,0.15)); root.add_widget(self.info)

        grid=GridLayout(cols=3,spacing=10,size_hint=(1,0.4))
        self.h=Label(text="12",font_size="24sp",color=(1,1,1,1))
        self.m=Label(text="00",font_size="24sp",color=(1,1,1,1))
        self.ap=Label(text="AM",font_size="24sp",color=(1,1,1,1))
        arrows=[("▲",self._ch_h,1),("▲",self._ch_m,1),("▲",self._ch_ap,1),
                ("▼",self._ch_h,-1),("▼",self._ch_m,-1),("▼",self._ch_ap,-1)]
        for idx,(sym,fn,stp) in enumerate(arrows):
            b=Button(text=sym,font_size="24sp",background_color=(0.2,0.4,0.8,1))
            b.bind(on_press=lambda i,f=fn,s=stp:f(s)); grid.add_widget(b)
            if idx==2: grid.add_widget(self.h);grid.add_widget(self.m);grid.add_widget(self.ap)
        root.add_widget(grid)

        nav=BoxLayout(size_hint=(1,0.15),spacing=10)
        nav.add_widget(Button(text="Back",background_color=(0.2,0.4,0.8,1),
                              on_press=lambda *_:setattr(self.manager,"current","home")))
        nav.add_widget(Button(text="OK",background_color=(0.3,0.7,0.9,1),
                              on_press=self._confirm))
        root.add_widget(nav); self.add_widget(root)

    def _upd(self,i,v): self.bg.size=i.size; self.bg.pos=i.pos
    def set_day_time(self,d,t): self.day,self.tod=d,t; self.info.text=f"{d} — {t}"
    def _ch_h(self,s): self.h.text=f"{((int(self.h.text)-1+s)%12+1):02}"
    def _ch_m(self,s): self.m.text=f"{(int(self.m.text)+s)%60:02}"
    def _ch_ap(self,_): self.ap.text="PM" if self.ap.text=="AM" else "AM"

    def _confirm(self,*_):
        hr=int(self.h.text)%12 + (12 if self.ap.text=="PM" else 0)
        t24=f"{hr:02}:{self.m.text}"
        disp=f"{self.h.text}:{self.m.text} {self.ap.text}"
        getattr(schedule.every(),self.day.lower()).at(t24).do(trigger_alarm,self.day,disp)
        setattr(self.manager,"current","home")


class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root=BoxLayout(orientation="vertical",padding=10,spacing=10)
        with root.canvas.before:
            Color(0.05,0.05,0.20,1); self.bg=Rectangle(size=root.size,pos=root.pos)
        root.bind(size=self._upd,pos=self._upd)
        root.add_widget(Label(text="Settings",font_size="24sp",color=(1,1,1,1)))
        root.add_widget(Button(text="Sync Pi RTC",background_color=(0.3,0.7,0.9,1),
                               on_press=lambda *_:os.system("sudo timedatectl set-ntp true")))
        root.add_widget(Button(text="Back",background_color=(0.2,0.4,0.8,1),
                               on_press=lambda *_:setattr(self.manager,"current","home")))
        self.add_widget(root)
    def _upd(self,i,v): self.bg.size=i.size; self.bg.pos=i.pos


# ───────── App wrapper ─────────
class PillSchedulerApp(App):
    def build(self):
        sm=ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(TimeScreen(name="time"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm
    def on_start(self):
        threading.Thread(target=scheduler_loop,daemon=True).start()


if __name__ == "__main__":
    PillSchedulerApp().run()
