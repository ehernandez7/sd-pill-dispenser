"""
pill_scheduler_with_motor.py
----------------------------
GUI pill-box scheduler (14 slots) + LED flash + audio + stepper motor
"""

from kivy.app            import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout     import BoxLayout
from kivy.uix.gridlayout    import GridLayout
from kivy.uix.label         import Label
from kivy.uix.button        import Button
from kivy.uix.popup         import Popup
from kivy.clock             import Clock
from kivy.graphics          import Color, Rectangle

import schedule, threading, os, time
from datetime import datetime, timedelta

# ───────── optional hardware (wrap in try/except so code runs on a laptop) ─────────
try:
    from gpiozero import LED, DigitalOutputDevice
    led = LED(14)                            # BCM 14
    DIR_PIN, STEP_PIN = 21, 20               # BCM pins to A4988/DRV driver
    dir_pin  = DigitalOutputDevice(DIR_PIN)
    step_pin = DigitalOutputDevice(STEP_PIN)
    HW = True
except Exception:
    led = None
    HW  = False

try:
    import pygame
    pygame.mixer.init()
    ALARM_FILE = "Python Test/Good place.mp3"                 # put an MP3/WAV here
except Exception:
    pygame = None

# ───────── step pattern: 14 slots = 200 steps — see design spec ─────────
STEPS_PER_SLOT = [14,14,14,15,15,14,14,14,14,14,15,15,14,14]  # len==14, sum==200
current_slot = 0                                              # 0 = Sunday-Morning

def move_steps(n, forward=True, delay=0.002):
    """Blocking: pulse STEP pin n times."""
    if not HW:
        print(f"[motor-sim] move {n} steps {'fwd' if forward else 'rev'}")
        time.sleep(n*delay*2)
        return
    dir_pin.value = 1 if forward else 0
    for _ in range(n):
        step_pin.on();  time.sleep(delay)
        step_pin.off(); time.sleep(delay)

def rotate_to_slot(target):
    """Rotate the carousel forward to reach target slot id (0-13)."""
    global current_slot
    diff = (target - current_slot) % 14
    for i in range(diff):
        idx = (current_slot + i) % 14
        move_steps(STEPS_PER_SLOT[idx], forward=True)
    current_slot = target
    print(f"[motor] now at slot {current_slot}")

def reset_motor():
    rotate_to_slot(0)

# ───────── GUI + scheduler ─────────
days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

def trigger_alarm(day, disp_time, period):
    slot = days.index(day)*2 + (0 if period=="Morning" else 1)
    threading.Thread(target=rotate_to_slot, args=(slot,), daemon=True).start()
    Clock.schedule_once(lambda dt: AlarmPopup(day, disp_time).open(), 0)

class AlarmPopup(Popup):
    def __init__(self, day, when, **kw):
        super().__init__(**kw)
        self.title, self.size_hint = "⏰  Medicine Reminder  ⏰", (.8,.5)
        self.flash_int, self.on_state = .7, False

        lay = BoxLayout(orientation="vertical",padding=10,spacing=10)
        with lay.canvas.before:
            self.bg = Color(.05,.05,.2,1); self.rect = Rectangle(size=lay.size,pos=lay.pos)
        lay.bind(size=self._upd,pos=self._upd)

        self.msg = Label(text=f"[b]Time to take your medicine[/b]\n{day}  {when}",
                         markup=True,font_size="20sp",halign="center",color=(1,1,1,1))
        lay.add_widget(self.msg)
        btn_row = BoxLayout(size_hint=(1,.3),spacing=10)
        for txt,cb in (("Snooze 5 min",self._snooze),("Stop",self._stop)):
            b=Button(text=txt,font_size="18sp"); b.bind(on_press=cb); btn_row.add_widget(b)
        lay.add_widget(btn_row); self.content = lay

        self.ev = Clock.schedule_interval(self._flash,self.flash_int)
        self._start_audio_led()

    def _upd(self,i,v): self.rect.size=i.size; self.rect.pos=i.pos
    def _flash(self,_):
        self.on_state = not self.on_state
        self.bg.rgba = (.12,.12,.32,1) if self.on_state else (.05,.05,.2,1)
        self.msg.opacity = .6 if self.on_state else 1
        if led: (led.on() if self.on_state else led.off())

    def _start_audio_led(self):
        if pygame and os.path.exists(ALARM_FILE):
            try: pygame.mixer.music.load(ALARM_FILE); pygame.mixer.music.play(-1)
            except Exception as e: print("audio err:",e)

    def _stop_audio_led(self):
        if led: led.off()
        if pygame and pygame.mixer.get_init(): pygame.mixer.music.stop()

    def _snooze(self,*_):
        nxt = datetime.now()+timedelta(minutes=5)
        schedule.every().day.at(nxt.strftime("%H:%M")).do(
            trigger_alarm, nxt.strftime("%A"), nxt.strftime("%I:%M %p"),
            ("Evening" if nxt.hour>=12 else "Morning"))
        self._stop()
    def _stop(self,*_):
        if self.ev.is_triggered: self.ev.cancel()
        self._stop_audio_led(); self.dismiss()

class HomeScreen(Screen):
    def __init__(self,**kw):
        super().__init__(**kw); self.di=0
        root = BoxLayout(orientation="vertical",padding=10,spacing=10)
        with root.canvas.before: Color(.05,.05,.2,1); self.rect=Rectangle(size=root.size,pos=root.pos)
        root.bind(size=self._upd,pos=self._upd)
        root.add_widget(Label(text="Pill Container Scheduler",font_size="24sp",
                              color=(1,1,1,1),size_hint=(1,.15)))
        self.clock=Label(font_size="18sp",color=(1,1,1,1),size_hint=(1,.1))
        root.add_widget(self.clock); Clock.schedule_interval(lambda dt:self._tick(),1)

        nav=BoxLayout(size_hint=(1,.15))
        nav.add_widget(Button(text="<",background_color=(.2,.4,.8,1),
                              on_press=lambda *_:self._chg(-1)))
        self.day_lab=Label(text=days[self.di],font_size="20sp",color=(1,1,1,1))
        nav.add_widget(self.day_lab)
        nav.add_widget(Button(text=">",background_color=(.2,.4,.8,1),
                              on_press=lambda *_:self._chg(+1)))
        root.add_widget(nav)

        tod=BoxLayout(size_hint=(1,.2),spacing=10)
        for name in ("Morning","Evening"):
            tod.add_widget(Button(text=name,background_color=(.1,.6,.8,1),
                                  on_press=lambda inst,n=name:self._goto(n)))
        root.add_widget(tod)

        row=BoxLayout(size_hint=(1,.15),spacing=10)
        row.add_widget(Button(text="Test Alarm",background_color=(.3,.7,.9,1),
                              on_press=lambda *_:trigger_alarm(self.day_lab.text,
                                     datetime.now().strftime("%I:%M %p"),
                                     ("Evening" if datetime.now().hour>=12 else "Morning"))))
        row.add_widget(Button(text="Reset Motor",background_color=(.3,.5,.9,1),
                              on_press=lambda *_:threading.Thread(target=reset_motor,
                                                   daemon=True).start()))
        row.add_widget(Button(text="Settings",background_color=(.2,.5,.7,1),
                              on_press=lambda *_:setattr(self.manager,"current","settings")))
        root.add_widget(row); self.add_widget(root)

    def _upd(self,i,v): self.rect.size=i.size; self.rect.pos=i.pos
    def _tick(self): self.clock.text=datetime.now().strftime("%I:%M:%S %p")
    def _chg(self,s): self.di=(self.di+s)%7; self.day_lab.text=days[self.di]
    def _goto(self,period):
        ts=self.manager.get_screen("time"); ts.set_day_period(self.day_lab.text,period)
        setattr(self.manager,"current","time")

class TimeScreen(Screen):
    def __init__(self,**kw):
        super().__init__(**kw); self.day=self.period=""
        root=BoxLayout(orientation="vertical",padding=10,spacing=10)
        with root.canvas.before: Color(.05,.05,.2,1); self.rect=Rectangle(size=root.size,pos=root.pos)
        root.bind(size=self._upd,pos=self._upd)
        self.info=Label(font_size="20sp",color=(1,1,1,1),size_hint=(1,.15)); root.add_widget(self.info)

        grid=GridLayout(cols=3,spacing=10,size_hint=(1,.4))
        self.h=Label(text="08",font_size="24sp",color=(1,1,1,1))
        self.m=Label(text="00",font_size="24sp",color=(1,1,1,1))
        self.ap=Label(text="AM",font_size="24sp",color=(1,1,1,1))
        arr=[("▲",self._ch_h,1),("▲",self._ch_m,1),("▲",self._ch_ap,1),
             ("▼",self._ch_h,-1),("▼",self._ch_m,-1),("▼",self._ch_ap,-1)]
        for idx,(sym,fn,stp) in enumerate(arr):
            b=Button(text=sym,font_size="24sp",background_color=(.2,.4,.8,1))
            b.bind(on_press=lambda i,f=fn,s=stp:f(s)); grid.add_widget(b)
            if idx==2: grid.add_widget(self.h); grid.add_widget(self.m); grid.add_widget(self.ap)
        root.add_widget(grid)

        nav=BoxLayout(size_hint=(1,.15),spacing=10)
        nav.add_widget(Button(text="Back",background_color=(.2,.4,.8,1),
                              on_press=lambda *_:setattr(self.manager,"current","home")))
        nav.add_widget(Button(text="OK",background_color=(.3,.7,.9,1),
                              on_press=self._save))
        root.add_widget(nav); self.add_widget(root)

    def _upd(self,i,v): self.rect.size=i.size; self.rect.pos=i.pos
    def set_day_period(self,d,p): self.day,self.period=d,p; self.info.text=f"{d} — {p}"
    def _ch_h(self,s): self.h.text=f"{((int(self.h.text)-1+s)%12+1):02}"
    def _ch_m(self,s): self.m.text=f"{(int(self.m.text)+s)%60:02}"
    def _ch_ap(self,_): self.ap.text="PM" if self.ap.text=="AM" else "AM"

    def _save(self,*_):
        hr=int(self.h.text)%12 + (12 if self.ap.text=="PM" else 0)
        t24=f"{hr:02}:{self.m.text}"
        disp=f"{self.h.text}:{self.m.text} {self.ap.text}"
        getattr(schedule.every(),self.day.lower()).at(t24).do(
            trigger_alarm,self.day,disp,self.period)
        setattr(self.manager,"current","home")

class SettingsScreen(Screen):
    def __init__(self,**kw):
        super().__init__(**kw)
        root=BoxLayout(orientation="vertical",padding=10,spacing=10)
        with root.canvas.before: Color(.05,.05,.2,1); self.rect=Rectangle(size=root.size,pos=root.pos)
        root.bind(size=self._upd,pos=self._upd)
        root.add_widget(Label(text="Settings",font_size="24sp",color=(1,1,1,1)))
        root.add_widget(Button(text="Sync Pi RTC",background_color=(.3,.7,.9,1),
                               on_press=lambda *_:os.system("sudo timedatectl set-ntp true")))
        root.add_widget(Button(text="Back",background_color=(.2,.4,.8,1),
                               on_press=lambda *_:setattr(self.manager,"current","home")))
        self.add_widget(root)
    def _upd(self,i,v): self.rect.size=i.size; self.rect.pos=i.pos

class PillSchedulerApp(App):
    def build(self):
        sm=ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(TimeScreen(name="time"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm
    def on_start(self):
        threading.Thread(target=lambda: (schedule.run_pending() or time.sleep(1)),
                         daemon=True).start()

if __name__=="__main__":
    PillSchedulerApp().run()
