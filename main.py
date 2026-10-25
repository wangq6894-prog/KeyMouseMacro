# -*- coding: utf-8 -*-
"""
键鼠模拟器（图形化鼠标宏 / 键盘模拟工具）

功能：
  1. 模拟键盘按键或鼠标按键：单次按下、持续按住、连续按 N 次、无限连发
  2. 序列循环：按顺序执行一组动作——键盘为依次按键（如 1 2 3 4），鼠标为依次
     点击（如 左 右 左 右）；支持逐步间隔（如 1:5:2，毫秒）、循环轮数限制
  3. 随机化时间（±20% 浮动），让节奏更像人手（可选）
  4. 全局热键控制开始 / 停止（默认 F9 / F10，可自定义），在其他程序里同样有效
  5. 自动记住上次的设置（保存到同目录 config.json，删除该文件即恢复默认）
  6. 界面语言跟随系统：中文系统显示中文，其他显示英文（--lang=zh/en 可强制指定）

仅使用 Python 标准库（tkinter 画界面，ctypes 调用 Windows API），无需安装第三方库。
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
winmm = ctypes.windll.winmm   # timeBeginPeriod：提高定时器精度，让毫秒级间隔真正生效

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# ---------------- 多语言文本 ----------------
TEXTS = {
    "zh": {
        "title": "键鼠模拟器",
        "group_target": "模拟目标", "group_mode": "动作与参数",
        "group_hotkeys": "全局热键（在其他程序中同样有效）",
        "radio_key": "键盘按键", "radio_mouse": "鼠标按键",
        "capture_hint": "← 点击后按下要模拟的按键\n（捕获时请切换到英文输入法）",
        "mouse_label": "鼠标按键：",
        "mouse_left": "左键", "mouse_right": "右键", "mouse_middle": "中键",
        "mode_label": "动作模式：",
        "mode_once": "单次按下", "mode_hold": "持续按住", "mode_n": "连续按N次",
        "mode_forever": "无限连发", "mode_seq": "序列循环",
        "press_label": "每次按下时长(毫秒)：", "interval_label": "两次动作间隔(毫秒)：",
        "times_label": "次数：",
        "seq_label": "序列：",
        "seq_hint_key": "用空格分隔，如：1 2 3 4 或 q e r f1；空格键写 space 或“空格”\n循环间隔是一轮全部按完后的等待时间",
        "seq_hint_mouse": "用空格分隔，可写：左/右/中（或 左键/右键/中键），如：左 右 左 右\n循环间隔是一轮全部按完后的等待时间",
        "stepint_label": "逐步间隔(毫秒)：",
        "stepint_hint": "用冒号分隔、依次对应每一步之后的等待，如 1:5:2；\n第 n 个间隔会替代“循环间隔”；没写到的步用默认间隔；个数不能多于步数",
        "cycle_label": "循环间隔(毫秒)：", "rounds_label": "循环轮数(0=无限)：",
        "hot_start_label": "开始：", "hot_stop_label": "停止：",
        "btn_start": "开始", "btn_stop": "停止",
        "chk_topmost": "窗口置顶", "chk_jitter": "间隔随机±20%",
        "hint_bottom": "提示：热键不要与要模拟的按键相同；部分游戏需以管理员身份运行本工具；\n游戏里“持续按住”无效时可改用“无限连发”。",
        "status_idle": "空闲 — 设置好后按 F9 或点击“开始”",
        "status_running": "运行中…（按 %s 停止）", "status_stopping": "正在停止…",
        "status_stopped": "已停止（共 %d 次）", "status_finished": "已完成（共 %d 次）",
        "count_fmt": "已执行 %d 次", "count_rounds_fmt": "已执行 %d 次 / %d 轮",
        "count_holding": "按住中…（按停止热键结束）",
        "not_set": "未设置", "capturing": "请按键…(Esc取消)", "keycode_fmt": "键码%d",
        "err_num_title": "参数错误", "err_num_body": "“%s”必须是数字。",
        "err_nokey_title": "尚未设置按键",
        "err_nokey_body": "请先点击“点击捕获”按钮并按下要模拟的按键。",
        "err_conflict_title": "按键冲突",
        "err_conflict_single": "要模拟的按键和开始/停止热键相同，请先修改热键。",
        "err_conflict_seq": "序列里有和开始/停止热键相同的按键，请先修改热键。",
        "err_badkeys_title": "无法识别的按键",
        "err_badkeys_body": "以下按键无法识别：%s\n请用空格分隔，如：1 2 3 4、q e r f1。",
        "err_badmouse_title": "无法识别的内容",
        "err_badmouse_body": "以下内容无法识别：%s\n鼠标序列可写：左/右/中（或 左键/右键/中键）。",
        "err_empty_title": "序列为空",
        "err_empty_keys": "请先在“序列”输入框里填写要依次执行的按键。",
        "err_empty_mouse": "请先在“序列”输入框里填写要依次点击的鼠标按键，如：左 右 左 右。",
        "err_stepint_title": "逐步间隔格式错误",
        "err_stepint_body": "逐步间隔只能是冒号分隔的数字，如 1:5:2 或 2000:300:300。",
        "err_toomany_title": "逐步间隔太多",
        "err_toomany_body": "逐步间隔有 %d 个，但序列只有 %d 步，间隔数不能多于步数。",
    },
    "en": {
        "title": "Key & Mouse Simulator",
        "group_target": "Target", "group_mode": "Action & Parameters",
        "group_hotkeys": "Global hotkeys (work inside other programs)",
        "radio_key": "Keyboard key", "radio_mouse": "Mouse button",
        "capture_hint": "← Click, then press the key to simulate",
        "mouse_label": "Mouse button:",
        "mouse_left": "Left", "mouse_right": "Right", "mouse_middle": "Middle",
        "mode_label": "Mode:",
        "mode_once": "Press once", "mode_hold": "Hold down", "mode_n": "Press N times",
        "mode_forever": "Repeat forever", "mode_seq": "Sequence loop",
        "press_label": "Press duration (ms):", "interval_label": "Interval (ms):",
        "times_label": "Count:",
        "seq_label": "Sequence:",
        "seq_hint_key": "Space-separated, e.g. 1 2 3 4 or q e r f1; write the space key as 'space'\nLoop pause = wait after one full loop",
        "seq_hint_mouse": "Space-separated: left / right / middle, e.g. left right left right\nLoop pause = wait after one full loop",
        "stepint_label": "Per-step intervals (ms):",
        "stepint_hint": "Colon-separated waits after each step, e.g. 1:5:2;\nthe n-th one replaces the loop pause; unset steps use the default interval;\ncannot be more entries than steps",
        "cycle_label": "Loop pause (ms):", "rounds_label": "Loops (0 = endless):",
        "hot_start_label": "Start:", "hot_stop_label": "Stop:",
        "btn_start": "Start", "btn_stop": "Stop",
        "chk_topmost": "Always on top", "chk_jitter": "Jitter timing ±20%",
        "hint_bottom": "Tips: hotkeys must differ from simulated keys; some games need this tool run as admin;\nif 'Hold down' has no effect in a game, use 'Repeat forever' instead.",
        "status_idle": "Idle — press F9 or click Start when ready",
        "status_running": "Running… (press %s to stop)", "status_stopping": "Stopping…",
        "status_stopped": "Stopped (%d presses total)", "status_finished": "Finished (%d presses total)",
        "count_fmt": "%d presses", "count_rounds_fmt": "%d presses / %d loops",
        "count_holding": "Holding… (press the stop hotkey to end)",
        "not_set": "not set", "capturing": "Press a key… (Esc cancels)", "keycode_fmt": "Key %d",
        "err_num_title": "Invalid number", "err_num_body": "\"%s\" must be a number.",
        "err_nokey_title": "No key set",
        "err_nokey_body": "Click the capture button first and press the key to simulate.",
        "err_conflict_title": "Hotkey conflict",
        "err_conflict_single": "The simulated key is the same as the start/stop hotkey. Change the hotkey first.",
        "err_conflict_seq": "The sequence contains the start/stop hotkey. Change the hotkey first.",
        "err_badkeys_title": "Unrecognized keys",
        "err_badkeys_body": "Unrecognized: %s\nSeparate keys with spaces, e.g. 1 2 3 4 or q e r f1.",
        "err_badmouse_title": "Unrecognized input",
        "err_badmouse_body": "Unrecognized: %s\nMouse sequence accepts: left / right / middle.",
        "err_empty_title": "Empty sequence",
        "err_empty_keys": "Fill in the keys to press in order in the sequence box first.",
        "err_empty_mouse": "Fill in the mouse buttons to click in order first, e.g. left right left right.",
        "err_stepint_title": "Bad per-step intervals",
        "err_stepint_body": "Per-step intervals must be colon-separated numbers, e.g. 1:5:2 or 2000:300:300.",
        "err_toomany_title": "Too many intervals",
        "err_toomany_body": "%d interval entries but only %d steps; entries cannot exceed steps.",
    },
}


def detect_language():
    """根据 Windows 界面语言选择 UI 语言：中文 → zh，其他 → en。"""
    try:
        if kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x04:   # LANG_CHINESE
            return "zh"
    except Exception:
        pass
    return "en"


LANGUAGE = detect_language()


def T(key):
    return TEXTS.get(LANGUAGE, TEXTS["en"]).get(key, TEXTS["zh"].get(key, key))


# ---------------- Windows 输入模拟常量 ----------------
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

VK_F9 = 0x78
VK_F10 = 0x79

# 需要标记为“扩展键”的常见虚拟键（方向键、Insert/Delete、右侧 Ctrl/Alt 等），
# 不加此标志部分程序无法识别这些键
EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24,   # PageUp PageDown End Home
    0x25, 0x26, 0x27, 0x28,   # 左 上 右 下
    0x2C, 0x2D, 0x2E,         # PrintScreen Insert Delete
    0x5B, 0x5C, 0x5D,         # 左Win 右Win 菜单键
    0x6F,                     # 小键盘 /
    0x90,                     # NumLock
    0xA3, 0xA5,               # 右Ctrl 右Alt
}

# ---------------- 序列文本解析用的 名称→键码/按键 表 ----------------
# 序列输入写法不随界面语言变化，中英文写法始终都接受
KEY_NAME_TO_VK = {chr(ord("a") + i): 0x41 + i for i in range(26)}
KEY_NAME_TO_VK.update({str(d): 0x30 + d for d in range(10)})
KEY_NAME_TO_VK.update({"f%d" % i: 0x70 + i - 1 for i in range(1, 25)})
KEY_NAME_TO_VK.update({
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
    "esc": 0x1B, "escape": 0x1B, "backspace": 0x08,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "win": 0x5B,
    # 中文别名（空格本身是分隔符，空格键只能写成单词）
    "空格": 0x20, "回车": 0x0D,
    "上": 0x26, "下": 0x28, "左": 0x25, "右": 0x27,
})

# 鼠标序列解析：token → MOUSE_BUTTONS 的键名（内部统一用中文键名做标识）
MOUSE_SEQ_TOKENS = {
    "左": "左键", "左键": "左键", "l": "左键", "left": "左键",
    "右": "右键", "右键": "右键", "r": "右键", "right": "右键",
    "中": "中键", "中键": "中键", "m": "中键", "middle": "中键",
}

MOUSE_LIST = ["左键", "右键", "中键"]   # 内部标识，界面显示走 T()

VkKeyScanW = user32.VkKeyScanW
VkKeyScanW.restype = ctypes.c_short
VkKeyScanW.argtypes = (ctypes.c_wchar,)


def parse_key_sequence(text):
    """把 "1 2 3 4"、"q e r f1" 这样的文本解析成虚拟键码列表。

    返回 (键码列表, 无法识别的词列表)。单个符号字符（如 - = [）按主键盘
    键位解析（不含 Shift），字母数字和 F1~F24 直接查表。
    """
    vks, bad = [], []
    for tok in text.split():
        name = tok.lower()
        if name in KEY_NAME_TO_VK:
            vks.append(KEY_NAME_TO_VK[name])
        elif len(tok) == 1:
            vk = VkKeyScanW(tok) & 0xFF
            if vk and vk != 0xFF:
                vks.append(vk)
            else:
                bad.append(tok)
        else:
            bad.append(tok)
    return vks, bad


def parse_mouse_sequence(text):
    """把 "左 右 左 右" / "left right left right" 解析成鼠标按键名列表。"""
    buttons, bad = [], []
    for tok in text.split():
        button = MOUSE_SEQ_TOKENS.get(tok.lower())
        if button:
            buttons.append(button)
        else:
            bad.append(tok)
    return buttons, bad


def parse_step_intervals(text):
    """解析逐步间隔文本，如 "1:5:2"（单位毫秒，允许全角冒号）。

    返回 (毫秒列表, 错误说明)。空文本返回 ([], None)。
    """
    text = text.strip()
    if not text:
        return [], None
    values = []
    for part in text.replace("：", ":").split(":"):
        part = part.strip()
        if not part.isdigit():
            return [], "bad"
        values.append(max(1, min(600000, int(part))))
    return values, None


# ---------------- SendInput 结构体定义 ----------------
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG), ("dy", wt.LONG),
        ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
        ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD), ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD), ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


SendInput = user32.SendInput
SendInput.argtypes = (wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
SendInput.restype = wt.UINT

GetAsyncKeyState = user32.GetAsyncKeyState
GetAsyncKeyState.restype = ctypes.c_short
GetAsyncKeyState.argtypes = (ctypes.c_int,)


def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def key_down(vk):
    flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0
    scan = user32.MapVirtualKeyW(vk, 0)
    _send(INPUT(type=INPUT_KEYBOARD,
                u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags))))


def key_up(vk):
    flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0)
    scan = user32.MapVirtualKeyW(vk, 0)
    _send(INPUT(type=INPUT_KEYBOARD,
                u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags))))


MOUSE_BUTTONS = {
    "左键": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "右键": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "中键": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


def mouse_down(button):
    _send(INPUT(type=INPUT_MOUSE,
                u=_INPUTUNION(mi=MOUSEINPUT(dwFlags=MOUSE_BUTTONS[button][0]))))


def mouse_up(button):
    _send(INPUT(type=INPUT_MOUSE,
                u=_INPUTUNION(mi=MOUSEINPUT(dwFlags=MOUSE_BUTTONS[button][1]))))


# ---------------- 模拟引擎（后台线程执行，通过队列与界面通信） ----------------
MODE_ONCE, MODE_HOLD, MODE_N, MODE_FOREVER, MODE_SEQ = "once", "hold", "n", "forever", "seq"
MODE_MAP = [MODE_ONCE, MODE_HOLD, MODE_N, MODE_FOREVER, MODE_SEQ]


def mode_names_local():
    """动作模式的界面显示名（顺序与 MODE_MAP 一致）。"""
    return [T("mode_once"), T("mode_hold"), T("mode_n"), T("mode_forever"), T("mode_seq")]


class MacroEngine:
    """actions 是 [(press, release), ...] 列表：单键模式只有一项，
    序列模式按顺序执行每一项（键盘按键或鼠标点击通用）。"""

    def __init__(self, event_queue):
        self._queue = event_queue
        self._stop = threading.Event()
        self._thread = None
        self.running = False

    def start(self, actions, mode, press_ms=30, interval_ms=100, times=10,
              cycle_ms=0, step_intervals=None, rounds=0, jitter=False):
        self._stop.clear()
        self.running = True
        self._thread = threading.Thread(
            target=self._run,
            args=(actions, mode, press_ms, interval_ms, times, cycle_ms,
                  step_intervals or [], rounds, jitter),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop.set()

    def join(self, timeout):
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)

    def _run(self, actions, mode, press_ms, interval_ms, times,
             cycle_ms, step_intervals, rounds, jitter):
        count = 0
        last_report = 0.0
        release_fn = None    # 记录当前按下的键，异常停止时保证松开

        def wait(ms):
            # 所有等待统一走这里：可被停止信号立即打断；开启随机化时 ±20% 浮动
            if ms <= 0:
                return
            if jitter:
                ms *= random.uniform(0.8, 1.2)
            self._stop.wait(ms / 1000)

        # Windows 默认定时器精度约 15.6 毫秒，不调高的话 1~15 毫秒的间隔全部不准
        winmm.timeBeginPeriod(1)
        try:
            if mode == MODE_ONCE:
                press, release = actions[0]
                release_fn = release
                press()
                wait(press_ms)
                release()
                count = 1
            elif mode == MODE_HOLD:
                press, release = actions[0]
                release_fn = release
                press()
                self._queue.put(("hold", None))
                self._stop.wait()                  # 一直按住，直到收到停止信号
                count = 1
            elif mode == MODE_SEQ:
                n = len(actions)
                rounds_done = 0
                while not self._stop.is_set() and (rounds <= 0 or rounds_done < rounds):
                    finished = False
                    for i, (press, release) in enumerate(actions):
                        if self._stop.is_set():
                            break
                        release_fn = release
                        press()
                        wait(press_ms)
                        release()
                        count += 1
                        now = time.monotonic()
                        if now - last_report >= 0.1:
                            last_report = now
                            self._queue.put(("count", count))
                        if i < n - 1:              # 步与步之间的等待：优先逐步间隔
                            wait(step_intervals[i] if i < len(step_intervals) else interval_ms)
                    else:
                        finished = True            # 本轮没有被中途打断
                    if not finished:
                        break
                    rounds_done += 1
                    self._queue.put(("count", (count, rounds_done)))
                    if self._stop.is_set() or (rounds > 0 and rounds_done >= rounds):
                        break
                    # 一轮结束后的等待：最后一步若有专属间隔则替代循环间隔
                    if len(step_intervals) >= n:
                        wait(step_intervals[n - 1])
                    else:
                        wait(cycle_ms)
            else:
                press, release = actions[0]
                release_fn = release
                total = times if mode == MODE_N else None
                while not self._stop.is_set() and (total is None or count < total):
                    press()
                    wait(press_ms)
                    release()
                    count += 1
                    now = time.monotonic()
                    if now - last_report >= 0.1 or (total is not None and count == total):
                        last_report = now
                        self._queue.put(("count", count))
                    if total is None or count < total:
                        wait(interval_ms)
        finally:
            try:
                if release_fn:
                    release_fn()     # 无论正常结束还是中途停止，都保证松开按键
            except Exception:
                pass
            winmm.timeEndPeriod(1)
            self.running = False
            self._queue.put(("done", count))


# ---------------- 按键捕获控件 ----------------
class KeyCaptureButton(ttk.Frame):
    """点击按钮后按下任意键盘按键即可完成捕获（Esc 取消）。"""

    def __init__(self, master, vk=0, name="", on_change=None, width=14):
        super().__init__(master)
        self.vk = vk
        self.name = name or (T("not_set") if not vk else T("keycode_fmt") % vk)
        self.on_change = on_change
        self._capturing = False
        self._button = ttk.Button(self, text=self.name, width=width,
                                  command=self._begin_capture)
        self._button.pack()
        self._button.bind("<KeyPress>", self._on_key)
        self._button.bind("<FocusOut>", lambda e: self._cancel_capture())

    @property
    def capturing(self):
        return self._capturing

    def set_key(self, vk, name):
        self.vk = vk
        self.name = name
        self._button.config(text=self.name)

    def set_enabled(self, enabled):
        if not enabled:
            self._cancel_capture()
        self._button.state(["!disabled"] if enabled else ["disabled"])

    def _begin_capture(self):
        self._capturing = True
        self._button.config(text=T("capturing"))
        self._button.focus_set()

    def _cancel_capture(self):
        if self._capturing:
            self._capturing = False
            self._button.config(text=self.name)

    def _on_key(self, event):
        if not self._capturing:
            return
        if event.keysym == "Escape":
            self._cancel_capture()
            return "break"
        # 某些输入法/组合键下拿不到键码，忽略本次按键，继续等待
        if not event.keycode:
            return "break"
        # Windows 下 tkinter 的 keycode 就是虚拟键码，可直接用于 SendInput
        self.vk = event.keycode
        self.name = event.keysym or event.char or (T("keycode_fmt") % self.vk)
        self._capturing = False
        self._button.config(text=self.name)
        if self.on_change:
            self.on_change()
        return "break"       # 阻止空格/回车触发按钮本身


# ---------------- 主界面 ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title(T("title"))
        root.resizable(False, False)

        self.queue = queue.Queue()
        self.engine = MacroEngine(self.queue)
        self._user_stopped = False

        self._build_ui()

        threading.Thread(target=self._watch_hotkeys, daemon=True).start()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll()

    # ---------- 界面 ----------
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.grid(sticky="nsew")

        # -- 模拟目标 --
        f1 = ttk.LabelFrame(main, text=T("group_target"), padding=8)
        f1.grid(row=0, column=0, sticky="we", pady=(0, 6))
        self.target_type = tk.StringVar(value="key")
        ttk.Radiobutton(f1, text=T("radio_key"), variable=self.target_type,
                        value="key", command=self._switch_target).grid(row=0, column=0, padx=(0, 20))
        self.radio_mouse = ttk.Radiobutton(f1, text=T("radio_mouse"), variable=self.target_type,
                                           value="mouse", command=self._switch_target)
        self.radio_mouse.grid(row=0, column=1)

        self.key_frame = ttk.Frame(f1)
        self.key_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.key_capture = KeyCaptureButton(self.key_frame, on_change=self._update_button_labels)
        self.key_capture.grid(row=0, column=0)
        ttk.Label(self.key_frame, text=T("capture_hint"),
                  foreground="#8b949e", justify="left").grid(row=0, column=1, padx=(8, 0))

        self.mouse_frame = ttk.Frame(f1)
        self.mouse_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(self.mouse_frame, text=T("mouse_label")).grid(row=0, column=0)
        self.mouse_button = ttk.Combobox(
            self.mouse_frame,
            values=[T("mouse_left"), T("mouse_right"), T("mouse_middle")],
            state="readonly", width=8)
        self.mouse_button.current(0)
        self.mouse_button.grid(row=0, column=1)
        self.mouse_frame.grid_remove()      # 默认显示键盘目标

        # -- 动作与参数 --
        f2 = ttk.LabelFrame(main, text=T("group_mode"), padding=8)
        f2.grid(row=1, column=0, sticky="we", pady=6)

        ttk.Label(f2, text=T("mode_label")).grid(row=0, column=0, sticky="w", pady=2)
        self.mode_combo = ttk.Combobox(f2, values=mode_names_local(), state="readonly", width=14)
        self.mode_combo.current(3)          # 默认“无限连发”
        self.mode_combo.grid(row=0, column=1, sticky="w")
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        # 序列循环模式的输入区（仅在该模式下显示）
        # 键盘序列与鼠标序列分开记忆，切换模拟目标时自动换内容
        self.seq_frame = ttk.Frame(f2)
        self.seq_frame.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 2))
        ttk.Label(self.seq_frame, text=T("seq_label")).grid(row=0, column=0, sticky="w")
        self.seq_var = tk.StringVar(value="")
        self._key_seq_saved = ""
        self._mouse_seq_saved = ""
        self._last_target = None
        ttk.Entry(self.seq_frame, textvariable=self.seq_var, width=22).grid(row=0, column=1, sticky="w")
        self.seq_hint = ttk.Label(self.seq_frame, text="", foreground="#8b949e", justify="left")
        self.seq_hint.grid(row=1, column=0, columnspan=2, sticky="w")

        ttk.Label(self.seq_frame, text=T("stepint_label")).grid(row=2, column=0, sticky="w")
        self.stepint_var = tk.StringVar(value="")
        ttk.Entry(self.seq_frame, textvariable=self.stepint_var, width=22).grid(row=2, column=1, sticky="w")
        ttk.Label(self.seq_frame, text=T("stepint_hint"),
                  foreground="#8b949e", justify="left").grid(row=3, column=0, columnspan=2, sticky="w")

        ttk.Label(self.seq_frame, text=T("cycle_label")).grid(row=4, column=0, sticky="w", pady=(4, 0))
        self.cycle_var = tk.StringVar(value="1000")
        ttk.Spinbox(self.seq_frame, from_=1, to=600000, textvariable=self.cycle_var,
                    width=8).grid(row=4, column=1, sticky="w", pady=(4, 0))

        ttk.Label(self.seq_frame, text=T("rounds_label")).grid(row=5, column=0, sticky="w")
        self.rounds_var = tk.StringVar(value="0")
        ttk.Spinbox(self.seq_frame, from_=0, to=1000000, textvariable=self.rounds_var,
                    width=8).grid(row=5, column=1, sticky="w")
        self.seq_frame.grid_remove()

        self.press_var = tk.StringVar(value="30")
        ttk.Label(f2, text=T("press_label")).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Spinbox(f2, from_=1, to=5000, textvariable=self.press_var, width=8).grid(row=2, column=1, sticky="w")

        self.interval_var = tk.StringVar(value="100")
        ttk.Label(f2, text=T("interval_label")).grid(row=3, column=0, sticky="w", pady=2)
        ttk.Spinbox(f2, from_=1, to=60000, textvariable=self.interval_var, width=8).grid(row=3, column=1, sticky="w")

        self.times_var = tk.StringVar(value="10")
        ttk.Label(f2, text=T("times_label")).grid(row=4, column=0, sticky="w", pady=2)
        self.times_spin = ttk.Spinbox(f2, from_=1, to=1000000, textvariable=self.times_var, width=8)
        self.times_spin.grid(row=4, column=1, sticky="w")

        # -- 热键 --
        f3 = ttk.LabelFrame(main, text=T("group_hotkeys"), padding=8)
        f3.grid(row=2, column=0, sticky="we", pady=6)
        ttk.Label(f3, text=T("hot_start_label")).grid(row=0, column=0)
        self.hotkey_start = KeyCaptureButton(f3, vk=VK_F9, name="F9",
                                             on_change=self._update_button_labels)
        self.hotkey_start.grid(row=0, column=1, padx=(0, 24))
        ttk.Label(f3, text=T("hot_stop_label")).grid(row=0, column=2)
        self.hotkey_stop = KeyCaptureButton(f3, vk=VK_F10, name="F10",
                                            on_change=self._update_button_labels)
        self.hotkey_stop.grid(row=0, column=3)

        # -- 控制按钮 --
        f4 = ttk.Frame(main)
        f4.grid(row=3, column=0, sticky="we", pady=(6, 2))
        self.start_btn = ttk.Button(f4, text="%s (F9)" % T("btn_start"), command=self.start_macro)
        self.start_btn.grid(row=0, column=0, ipadx=10)
        self.stop_btn = ttk.Button(f4, text="%s (F10)" % T("btn_stop"), command=self.stop_macro)
        self.stop_btn.grid(row=0, column=1, padx=(10, 0), ipadx=10)
        self.topmost_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f4, text=T("chk_topmost"), variable=self.topmost_var,
                        command=self._toggle_topmost).grid(row=0, column=2, padx=(20, 0))
        self.jitter_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f4, text=T("chk_jitter"), variable=self.jitter_var).grid(row=0, column=3, padx=(16, 0))

        # -- 状态 --
        self.status_var = tk.StringVar(value=T("status_idle"))
        self.status_label = ttk.Label(main, textvariable=self.status_var,
                                      font=("", 13, "bold"), foreground="#656d76")
        self.status_label.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.count_var = tk.StringVar(value="")
        ttk.Label(main, textvariable=self.count_var,
                  font=("", 10), foreground="#57606a").grid(row=5, column=0, sticky="w")

        ttk.Label(main, text=T("hint_bottom"),
                  foreground="#8b949e", justify="left").grid(row=6, column=0, sticky="w", pady=(10, 0))

        # 读取上次保存的设置，再统一刷新一次界面状态
        self._load_config()
        self._switch_target()
        self._on_mode_change()
        self._update_button_labels()
        self._toggle_topmost()

    def _switch_target(self):
        now = self.target_type.get()
        if now != self._last_target:
            # 把当前序列存回对应一侧，再显示另一侧的序列
            if self._last_target == "key":
                self._key_seq_saved = self.seq_var.get()
            elif self._last_target == "mouse":
                self._mouse_seq_saved = self.seq_var.get()
            self.seq_var.set(self._mouse_seq_saved if now == "mouse" else self._key_seq_saved)
            self._last_target = now
        if now == "key":
            self.mouse_frame.grid_remove()
            self.key_frame.grid()
        else:
            self.key_frame.grid_remove()
            self.mouse_frame.grid()
        self._update_seq_hint()

    def _on_mode_change(self, event=None):
        mode = MODE_MAP[self.mode_combo.current()]
        is_seq = mode == MODE_SEQ
        self.times_spin.config(state="normal" if mode == MODE_N else "disabled")
        if is_seq:
            self.seq_frame.grid()
        else:
            self.seq_frame.grid_remove()
        # 序列模式下用不到单键捕获/单个鼠标键选择，置灰避免误解
        self.key_capture.set_enabled(not is_seq)
        self.mouse_button.config(state="disabled" if is_seq else "readonly")
        self._update_seq_hint()

    def _update_seq_hint(self):
        if self.target_type.get() == "mouse":
            self.seq_hint.config(text=T("seq_hint_mouse"))
        else:
            self.seq_hint.config(text=T("seq_hint_key"))

    def _update_button_labels(self):
        self.start_btn.config(text="%s (%s)" % (T("btn_start"), self.hotkey_start.name))
        self.stop_btn.config(text="%s (%s)" % (T("btn_stop"), self.hotkey_stop.name))

    def _toggle_topmost(self):
        self.root.attributes("-topmost", bool(self.topmost_var.get()))

    def _set_status(self, text, color):
        self.status_var.set(text)
        self.status_label.config(foreground=color)

    # ---------- 设置保存 / 读取 ----------
    def _save_config(self):
        if self.target_type.get() == "key":
            key_seq, mouse_seq = self.seq_var.get(), self._mouse_seq_saved
        else:
            key_seq, mouse_seq = self._key_seq_saved, self.seq_var.get()
        cfg = {
            "target_type": self.target_type.get(),
            "key_vk": self.key_capture.vk,
            "key_name": self.key_capture.name,
            "mouse_index": self.mouse_button.current(),
            "mode_index": self.mode_combo.current(),
            "press_ms": self.press_var.get(),
            "interval_ms": self.interval_var.get(),
            "times": self.times_var.get(),
            "seq_text": key_seq,
            "mouse_seq_text": mouse_seq,
            "step_intervals": self.stepint_var.get(),
            "cycle_ms": self.cycle_var.get(),
            "rounds": self.rounds_var.get(),
            "jitter": bool(self.jitter_var.get()),
            "hot_start": [self.hotkey_start.vk, self.hotkey_start.name],
            "hot_stop": [self.hotkey_stop.vk, self.hotkey_stop.name],
            "topmost": bool(self.topmost_var.get()),
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load_config(self):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            return
        try:
            if cfg.get("target_type") in ("key", "mouse"):
                self.target_type.set(cfg["target_type"])
            if cfg.get("key_vk"):
                self.key_capture.set_key(int(cfg["key_vk"]),
                                         cfg.get("key_name") or (T("keycode_fmt") % cfg["key_vk"]))
            if isinstance(cfg.get("mouse_index"), int) and 0 <= cfg["mouse_index"] < len(MOUSE_LIST):
                self.mouse_button.current(cfg["mouse_index"])
            if isinstance(cfg.get("mode_index"), int) and 0 <= cfg["mode_index"] < len(MODE_MAP):
                self.mode_combo.current(cfg["mode_index"])
            for var, key, lo, hi in ((self.press_var, "press_ms", 1, 5000),
                                     (self.interval_var, "interval_ms", 1, 60000),
                                     (self.times_var, "times", 1, 1000000),
                                     (self.cycle_var, "cycle_ms", 1, 600000),
                                     (self.rounds_var, "rounds", 0, 1000000)):
                value = cfg.get(key)
                if value is not None:
                    var.set(str(max(lo, min(hi, int(value)))))
            if isinstance(cfg.get("seq_text"), str):
                self._key_seq_saved = cfg["seq_text"]
            if isinstance(cfg.get("mouse_seq_text"), str):
                self._mouse_seq_saved = cfg["mouse_seq_text"]
            if isinstance(cfg.get("step_intervals"), str):
                self.stepint_var.set(cfg["step_intervals"])
            if isinstance(cfg.get("jitter"), bool):
                self.jitter_var.set(cfg["jitter"])
            for widget, key in ((self.hotkey_start, "hot_start"), (self.hotkey_stop, "hot_stop")):
                pair = cfg.get(key)
                if isinstance(pair, list) and pair and pair[0]:
                    widget.set_key(int(pair[0]), str(pair[1]))
            if isinstance(cfg.get("topmost"), bool):
                self.topmost_var.set(cfg["topmost"])
        except (KeyError, TypeError, ValueError):
            pass

    # ---------- 开始 / 停止 ----------
    def _read_int(self, var, lo, hi, what):
        try:
            return max(lo, min(hi, int(var.get())))
        except ValueError:
            messagebox.showwarning(T("err_num_title"), T("err_num_body") % what)
            return None

    def start_macro(self):
        if self.engine.running:
            return
        mode = MODE_MAP[self.mode_combo.current()]
        press_ms = self._read_int(self.press_var, 1, 5000, T("press_label"))
        interval_ms = self._read_int(self.interval_var, 1, 60000, T("interval_label"))
        times = self._read_int(self.times_var, 1, 1000000, T("times_label"))
        if press_ms is None or interval_ms is None or times is None:
            return

        cycle_ms = 0
        step_intervals = []
        rounds = 0
        actions = []
        if mode == MODE_SEQ:
            cycle_ms = self._read_int(self.cycle_var, 1, 600000, T("cycle_label"))
            rounds = self._read_int(self.rounds_var, 0, 1000000, T("rounds_label"))
            if cycle_ms is None or rounds is None:
                return
            if self.target_type.get() == "mouse":
                buttons, bad = parse_mouse_sequence(self.seq_var.get())
                if bad:
                    messagebox.showwarning(T("err_badmouse_title"),
                                           T("err_badmouse_body") % " ".join(bad))
                    return
                if not buttons:
                    messagebox.showwarning(T("err_empty_title"), T("err_empty_mouse"))
                    return
                actions = [(lambda b=btn: mouse_down(b), lambda b=btn: mouse_up(b))
                           for btn in buttons]
            else:
                vks, bad = parse_key_sequence(self.seq_var.get())
                if bad:
                    messagebox.showwarning(T("err_badkeys_title"),
                                           T("err_badkeys_body") % " ".join(bad))
                    return
                if not vks:
                    messagebox.showwarning(T("err_empty_title"), T("err_empty_keys"))
                    return
                hotkeys = (self.hotkey_start.vk, self.hotkey_stop.vk)
                if any(vk in hotkeys for vk in vks):
                    messagebox.showwarning(T("err_conflict_title"), T("err_conflict_seq"))
                    return
                actions = [(lambda v=vk: key_down(v), lambda v=vk: key_up(v)) for vk in vks]
            step_intervals, err = parse_step_intervals(self.stepint_var.get())
            if err:
                messagebox.showwarning(T("err_stepint_title"), T("err_stepint_body"))
                return
            if len(step_intervals) > len(actions):
                messagebox.showwarning(
                    T("err_toomany_title"),
                    T("err_toomany_body") % (len(step_intervals), len(actions)))
                return
        elif self.target_type.get() == "key":
            vk = self.key_capture.vk
            if not vk:
                messagebox.showwarning(T("err_nokey_title"), T("err_nokey_body"))
                return
            if vk in (self.hotkey_start.vk, self.hotkey_stop.vk):
                messagebox.showwarning(T("err_conflict_title"), T("err_conflict_single"))
                return
            actions = [(lambda: key_down(vk), lambda: key_up(vk))]
        else:
            button = MOUSE_LIST[self.mouse_button.current()]
            actions = [(lambda: mouse_down(button), lambda: mouse_up(button))]

        self._user_stopped = False
        self.count_var.set("")
        self.engine.start(actions, mode, press_ms, interval_ms, times,
                          cycle_ms=cycle_ms, step_intervals=step_intervals,
                          rounds=rounds, jitter=bool(self.jitter_var.get()))
        self._set_status(T("status_running") % self.hotkey_stop.name, "#1a7f37")
        self._save_config()

    def stop_macro(self):
        if self.engine.running:
            self._user_stopped = True
            self._set_status(T("status_stopping"), "#9a6700")
            self.engine.stop()

    # ---------- 全局热键监听（后台线程轮询） ----------
    def _watch_hotkeys(self):
        prev_start = prev_stop = False
        while True:
            start_down = bool(GetAsyncKeyState(self.hotkey_start.vk) & 0x8000)
            stop_down = bool(GetAsyncKeyState(self.hotkey_stop.vk) & 0x8000)
            if start_down and not prev_start:
                self.queue.put(("hotkey", "start"))
            if stop_down and not prev_stop:
                self.queue.put(("hotkey", "stop"))
            prev_start, prev_stop = start_down, stop_down
            time.sleep(0.03)

    def _any_capture_active(self):
        return (self.key_capture.capturing or self.hotkey_start.capturing
                or self.hotkey_stop.capturing)

    # ---------- 消息泵：后台线程 → 界面 ----------
    def _poll(self):
        try:
            while True:
                kind, value = self.queue.get_nowait()
                if kind == "hotkey":
                    # 正在捕获按键时忽略热键，避免设置热键的过程中误触发
                    if self._any_capture_active():
                        continue
                    if value == "start":
                        self.start_macro()
                    else:
                        self.stop_macro()
                elif kind == "count":
                    if isinstance(value, tuple):
                        self.count_var.set(T("count_rounds_fmt") % value)
                    else:
                        self.count_var.set(T("count_fmt") % value)
                elif kind == "hold":
                    self.count_var.set(T("count_holding"))
                elif kind == "done":
                    word = T("status_stopped") if self._user_stopped else T("status_finished")
                    color = "#656d76" if self._user_stopped else "#0969da"
                    self._set_status(word % value, color)
        except queue.Empty:
            pass
        self.root.after(40, self._poll)

    def _on_close(self):
        self._save_config()
        self.engine.stop()
        self.engine.join(1.0)     # 等后台线程松开按键后再退出
        self.root.destroy()


def main():
    global LANGUAGE
    # --lang=zh / --lang=en 可强制指定界面语言（默认跟随系统）
    for arg in sys.argv[1:]:
        if arg.startswith("--lang="):
            lang = arg.split("=", 1)[1]
            if lang in TEXTS:
                LANGUAGE = lang

    # 高 DPI 下让界面保持清晰
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    App(root)
    if "--selftest" in sys.argv:
        root.update()
        print("UI OK (%s)" % LANGUAGE)
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
