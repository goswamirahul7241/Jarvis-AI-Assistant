import sys
import time
import os
import glob
import subprocess
import json
import re
import threading
from datetime import datetime

try:
    import requests
    import pygame

    pygame.mixer.init()
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    import keyboard

    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

try:
    from STT import get_stt_instance, recognize_speech

    STT_AVAILABLE = True
except ImportError:
    STT_AVAILABLE = False

    def get_stt_instance():
        return None

    def recognize_speech(*args, **kwargs):
        return None


voice_listening = False
voice_thread = None
stt_instance = None


def start_voice_listening():
    global voice_listening, voice_thread, stt_instance

    if not STT_AVAILABLE:
        jarvis_print("STT not available. Install speechrecognition.")
        return

    if stt_instance is None:
        stt_instance = get_stt_instance()
        if stt_instance:
            stt_instance.calibrate_microphone(duration=2)

    voice_listening = True

    def voice_loop():
        global voice_listening
        print("\n  🎤 Voice listening started. Say something...\n")

        while voice_listening:
            try:
                if stt_instance:
                    text = stt_instance.listen_and_recognize(
                        timeout=5, phrase_time_limit=8
                    )
                    if text:
                        print(f"\n🎤 You said: {text}")
                        process_voice_input(text)
            except Exception as e:
                pass

    voice_thread = threading.Thread(target=voice_loop, daemon=True)
    voice_thread.start()


def stop_voice_listening():
    global voice_listening
    voice_listening = False
    print("\n  🎤 Voice listening stopped.\n")


def process_voice_input(user_input):
    global speech_enabled, voice_file_path, conversation_history

    try:
        print(f"\nYou > {user_input}")
        command = user_input.lower()

        if command in ["exit", "quit", "q", "goodbye", "bye"]:
            jarvis_print("Shutting down...")
            speak("Goodbye Sir!")
            stop_voice_listening()
            time.sleep(0.5)
            sys.exit(0)

        elif command in ["help", "h", "commands"]:
            jarvis_print(
                "Say: 'help', 'status', 'time', 'date', 'desktop', 'stop listening'"
            )

        elif command == "status":
            jarvis_print("All systems operational. AI: Online, Memory: Active")

        elif command == "time":
            from datetime import datetime

            jarvis_print(f"Time: {datetime.now().strftime('%I:%M %p')}")

        elif command == "date":
            from datetime import datetime

            jarvis_print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")

        elif command in ["stop listening", "stop voice", "sleep"]:
            stop_voice_listening()
            jarvis_print("Voice listening stopped.")

        elif (
            "open" in command
            or "play" in command
            or "create" in command
            or "remember" in command
        ):
            jarvis_print("Thinking...")
            response = ask_jarvis(user_input)
            jarvis_print(response)
            if speech_enabled and voice_file_path:
                speak(response)

        else:
            jarvis_print("Thinking...")
            response = ask_jarvis(user_input)
            jarvis_print(response)
            if speech_enabled and voice_file_path:
                speak(response)

    except Exception as e:
        print(f"  Error: {str(e)}")


JARVIS_BANNER = r"""
   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
                                                       
"""

POCKET_TTS_URL = "http://localhost:8000/tts"
GROQ_API_KEY = ""
GROQ_MODEL = "llama-3.1-8b-instant"
voice_file_path = None
speech_enabled = False
conversation_history = []
memory_data = {"facts": [], "preferences": {}, "conversations": []}

INTENT_PATTERNS = {
    "memory_store": [
        r"remember\s+(?:that\s+)?(.+)",
        r"store\s+(.+)",
        r"keep\s+in\s+mind\s+(.+)",
        r"dont\s+forget\s+(.+)",
        r"note\s+that\s+(.+)",
        r"save\s+(.+?)\s+as\s+(.+)",
        r"my\s+(\w+)\s+is\s+(.+)",
        r"i\s+(\w+)\s+(?:am|'m)\s+(.+)",
        r"(\w+)\s+is\s+(?:my\s+)?(.+)",
        r"call\s+me\s+(.+)",
        r"my\s+name\s+is\s+(.+)",
    ],
    "memory_retrieve": [
        r"what\s+(?:is|was)\s+my\s+(.+)",
        r"do\s+i\s+(.+)",
        r"recall\s+(.+)",
        r"remember\s+(?:my\s+)?(.+)",
        r"what\s+do\s+you\s+know\s+about\s+(.+)",
        r"tell\s+me\s+my\s+(.+)",
        r"what\s+i\s+told\s+you\s+about\s+(.+)",
    ],
    "task_execution": [
        r"open\s+(.+)",
        r"play\s+(.+)",
        r"create\s+(.+)",
        r"delete\s+(.+)",
        r"search\s+(.+)",
        r"find\s+(.+)",
        r"make\s+(.+)",
        r"show\s+(.+)",
    ],
    "think_deep": [
        r"think\s+(?:about|deep)\s+(.+)",
        r"analyze\s+(.+)",
        r"explain\s+(.+)",
        r"how\s+does\s+(.+)",
        r"why\s+(.+)",
        r"what\s+happens\s+if\s+(.+)",
    ],
}


def detect_intent(user_input):
    import re

    input_lower = user_input.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, input_lower):
                return intent
    return "chat"


def think_step(user_input, intent, memory_context):
    try:
        messages = [
            {
                "role": "system",
                "content": f"""You are JARVIS thinking module. Analyze the user input and plan your response.

User Input: {user_input}
Detected Intent: {intent}
Memory Context: {memory_context}

Think step-by-step:
1. What does the user want?
2. Do I need to use memory?
3. What tools should I use?
4. How should I respond?

Respond with your thinking in 1-2 sentences only.""",
            }
        ]
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 150,
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except:
        return None


def extract_memory(user_input):
    important_patterns = [
        (r"my\s+name\s+is\s+(.+)", "name"),
        (r"call\s+me\s+(.+)", "name"),
        (r"i\s+live\s+in\s+(.+)", "location"),
        (r"i\s+work\s+(?:at|as)\s+(.+)", "work"),
        (r"i\s+like\s+(.+)", "likes"),
        (r"i\s+hate\s+(.+)", "dislikes"),
        (r"my\s+birthday\s+is\s+(.+)", "birthday"),
        (r"my\s+email\s+is\s+(.+)", "email"),
        (r"my\s+phone\s+is\s+(.+)", "phone"),
        (r"(\w+)\s+is\s+my\s+(.+)", "custom"),
    ]
    import re

    extracted = []
    for pattern, key in important_patterns:
        match = re.search(pattern, user_input.lower())
        if match:
            value = match.group(1).strip()
            if key == "custom":
                key = match.group(1).strip()
            extracted.append((key, value))
    return extracted


def decide_action(intent, user_input, memory_context):
    try:
        messages = [
            {
                "role": "system",
                "content": f"""You are JARVIS decision module. Decide what action to take.

User Input: {user_input}
Detected Intent: {intent}
Memory: {memory_context}

Choose ONE action:
- memory_store: Store important info
- memory_retrieve: Recall stored info
- task_execution: Perform a task (open app, play music, etc)
- think_deep: Analyze deeply
- chat: General conversation

Respond with ONLY the action name.""",
            }
        ]
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 50,
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip().lower()
    except:
        return intent


DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
MEMORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.json"
)

APP_PATTERNS = {
    "chrome": {"win": "chrome", "web": "https://chrome.google.com"},
    "google chrome": {"win": "chrome", "web": "https://chrome.google.com"},
    "firefox": {"win": "firefox", "web": "https://www.mozilla.org/firefox"},
    "microsoft edge": {"win": "msedge", "web": "https://www.microsoft.com/edge"},
    "edge": {"win": "msedge", "web": "https://www.microsoft.com/edge"},
    "brave": {"win": "brave", "web": "https://brave.com"},
    "opera": {"win": "opera", "web": "https://www.opera.com"},
    "safari": {"win": "safari", "web": "https://www.apple.com/safari"},
    "vivaldi": {"win": "vivaldi", "web": "https://vivaldi.com"},
    "notepad": {"win": "notepad", "web": None},
    "vscode": {"win": "code", "web": "https://vscode.dev"},
    "visual studio code": {"win": "code", "web": "https://vscode.dev"},
    "sublime": {"win": "sublime_text", "web": "https://sublimemerge.com"},
    "atom": {"win": "atom", "web": "https://github.dev"},
    "spotify": {"win": "spotify", "web": "https://open.spotify.com"},
    "youtube music": {"win": "youtube music", "web": "https://music.youtube.com"},
    "apple music": {"win": "apple music", "web": "https://music.apple.com"},
    "soundcloud": {"win": "soundcloud", "web": "https://soundcloud.com"},
    "amazon music": {"win": "amazon music", "web": "https://music.amazon.com"},
    "discord": {"win": "discord", "web": "https://discord.com/app"},
    "telegram": {"win": "telegram", "web": "https://web.telegram.org"},
    "whatsapp": {"win": "whatsapp", "web": "https://web.whatsapp.com"},
    "slack": {"win": "slack", "web": "https://slack.com/signin"},
    "teams": {"win": "teams", "web": "https://teams.microsoft.com"},
    "zoom": {"win": "zoom", "web": "https://zoom.us"},
    "skype": {"win": "skype", "web": "https://web.skype.com"},
    "messenger": {"win": "messenger", "web": "https://www.messenger.com"},
    "instagram": {"win": "instagram", "web": "https://www.instagram.com"},
    "facebook": {"win": "facebook", "web": "https://www.facebook.com"},
    "twitter": {"win": "twitter", "web": "https://twitter.com"},
    "x": {"win": "x", "web": "https://x.com"},
    "tiktok": {"win": "tiktok", "web": "https://www.tiktok.com"},
    "snapchat": {"win": "snapchat", "web": "https://web.snapchat.com"},
    "reddit": {"win": "reddit", "web": "https://www.reddit.com"},
    "linkedin": {"win": "linkedin", "web": "https://www.linkedin.com"},
    "pinterest": {"win": "pinterest", "web": "https://www.pinterest.com"},
    "twitch": {"win": "twitch", "web": "https://www.twitch.tv"},
    "kick": {"win": "kick", "web": "https://www.kick.com"},
    "youtube": {"win": "youtube", "web": "https://www.youtube.com"},
    "netflix": {"win": "netflix", "web": "https://www.netflix.com"},
    "amazon prime": {"win": "amazon prime video", "web": "https://www.primevideo.com"},
    "prime video": {"win": "prime video", "web": "https://www.primevideo.com"},
    "hotstar": {"win": "hotstar", "web": "https://www.hotstar.com"},
    "disney+": {"win": "disney+", "web": "https://www.disneyplus.com"},
    "hulu": {"win": "hulu", "web": "https://www.hulu.com"},
    "hbomax": {"win": "hbomax", "web": "https://www.max.com"},
    "max": {"win": "max", "web": "https://www.max.com"},
    "spotify web": {"win": None, "web": "https://open.spotify.com"},
    "youtube web": {"win": None, "web": "https://www.youtube.com"},
    "word": {"win": "winword", "web": "https://word.office.com"},
    "excel": {"win": "excel", "web": "https://excel.office.com"},
    "powerpoint": {"win": "powerpnt", "web": "https://powerpoint.office.com"},
    "onenote": {"win": "onenote", "web": "https://www.onenote.com"},
    "outlook": {"win": "outlook", "web": "https://outlook.live.com"},
    "gmail": {"win": "gmail", "web": "https://mail.google.com"},
    "google drive": {"win": "google drive", "web": "https://drive.google.com"},
    "dropbox": {"win": "dropbox", "web": "https://www.dropbox.com"},
    "icloud": {"win": "icloud", "web": "https://www.icloud.com"},
    "calc": {"win": "calc", "web": None},
    "calculator": {"win": "calc", "web": None},
    "paint": {"win": "mspaint", "web": "https://jspaint.app"},
    "wordpad": {"win": "wordpad", "web": None},
    "camera": {"win": "microsoft.windows.camera:", "web": None},
    "photos": {"win": "photos", "web": None},
    "settings": {"win": "ms-settings:", "web": None},
    "file explorer": {"win": "explorer", "web": None},
    "explorer": {"win": "explorer", "web": None},
    "cmd": {"win": "cmd", "web": None},
    "command prompt": {"win": "cmd", "web": None},
    "powershell": {"win": "powershell", "web": "https://vscode.dev"},
    "task manager": {"win": "taskmgr", "web": None},
    "control panel": {"win": "control", "web": None},
    "device manager": {"win": "devmgmt.msc", "web": None},
    "registry": {"win": "regedit", "web": None},
    "snipping tool": {"win": "snippingtool", "web": None},
    "clipboard": {"win": "ms-clipboard", "web": None},
    "store": {"win": "ms-windows-store", "web": "https://apps.microsoft.com"},
    "microsoft store": {"win": "ms-windows-store", "web": "https://apps.microsoft.com"},
    "whatsapp web": {"win": None, "web": "https://web.whatsapp.com"},
    "telegram web": {"win": None, "web": "https://web.telegram.org"},
    "gpt": {"win": None, "web": "https://chat.openai.com"},
    "chatgpt": {"win": None, "web": "https://chat.openai.com"},
    "claude": {"win": None, "web": "https://claude.ai"},
    "gemini": {"win": None, "web": "https://gemini.google.com"},
    "midjourney": {"win": None, "web": "https://www.midjourney.com"},
    "canva": {"win": None, "web": "https://www.canva.com"},
    "figma": {"win": None, "web": "https://www.figma.com"},
    "notion": {"win": None, "web": "https://www.notion.so"},
    "evernote": {"win": None, "web": "https://www.evernote.com"},
    "trello": {"win": None, "web": "https://trello.com"},
    "asana": {"win": None, "web": "https://asana.com"},
    "github": {"win": None, "web": "https://github.com"},
    "gitlab": {"win": None, "web": "https://gitlab.com"},
    "bitbucket": {"win": None, "web": "https://bitbucket.org"},
    "stackoverflow": {"win": None, "web": "https://stackoverflow.com"},
    "whatsapp": {"win": "whatsapp", "web": "https://web.whatsapp.com"},
    "signal": {"win": "signal", "web": "https://signal.org"},
    "viber": {"win": "viber", "web": "https://web.viber.com"},
    "wechat": {"win": "wechat", "web": "https://web.wechat.com"},
    "line": {"win": "line", "web": "https://line.me"},
    "steam": {"win": "steam", "web": "https://store.steampowered.com"},
    "epic games": {"win": "epicgameslauncher", "web": "https://www.epicgames.com"},
    "epic": {"win": "epicgameslauncher", "web": "https://www.epicgames.com"},
    "gta": {"win": None, "web": "https://www.rockstargames.com/gta-online"},
    "minecraft": {"win": "minecraft", "web": "https://www.minecraft.net"},
    "valorant": {"win": "valorant", "web": "https://playvalorant.com"},
    "fortnite": {"win": "fortnite", "web": "https://www.fortnite.com"},
    "pubg": {"win": "pubg", "web": "https://pubg.com"},
    "cod": {"win": "callofduty", "web": "https://www.callofduty.com"},
    "whatsapp": {"win": "whatsapp", "web": "https://web.whatsapp.com"},
}

MUSIC_PLATFORMS = {
    "spotify": "https://open.spotify.com",
    "youtube music": "https://music.youtube.com",
    "youtube": "https://www.youtube.com",
    "apple music": "https://music.apple.com",
    "soundcloud": "https://soundcloud.com",
    "amazon music": "https://music.amazon.com",
    "gaana": "https://gaana.com",
    "jio saavn": "https://www.jiosaavn.com",
    "saavn": "https://www.jiosaavn.com",
    "wynk": "https://wynk.in",
    "pandora": "https://www.pandora.com",
    "deezer": "https://www.deezer.com",
    "tidal": "https://tidal.com",
    "napster": "https://napster.com",
    "iheartradio": "https://www.iheart.com",
    "shazam": {"win": "shazam", "web": "https://www.shazam.com"},
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open any website in the default browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open"},
                    "reason": {"type": "string", "description": "Why opening this URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open any application - tries Windows app first, falls back to web version in browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the app to open",
                    },
                    "song": {
                        "type": "string",
                        "description": "Optional: song name to play",
                    },
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play music - asks user which platform they want to use",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {"type": "string", "description": "Song name to play"},
                    "platform": {
                        "type": "string",
                        "description": "Platform: spotify, youtube, apple music, etc. If not specified, ask user",
                    },
                },
                "required": ["song"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder on the desktop",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "Name of the folder to create",
                    }
                },
                "required": ["folder_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file on the desktop with optional content",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Name of the file with extension",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write in the file",
                    },
                },
                "required": ["file_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_item",
            "description": "Delete a file or folder from desktop",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of file or folder to delete",
                    },
                    "type": {
                        "type": "string",
                        "description": "Type: 'file' or 'folder'",
                    },
                },
                "required": ["name", "type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_desktop",
            "description": "List all files and folders on the desktop",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a text file from desktop",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Name of the file to read",
                    }
                },
                "required": ["file_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store important information in JARVIS's memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key/name for the memory"},
                    "value": {
                        "type": "string",
                        "description": "Information to remember",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
]


def load_memory():
    global memory_data
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
    except:
        pass


def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, indent=2)
    except:
        pass


def remember(key, value):
    memory_data["facts"].append(
        {"key": key, "value": value, "time": datetime.now().isoformat()}
    )
    memory_data["preferences"][key] = value
    save_memory()
    return f"Remembered: {key} = {value}"


def recall(key):
    if key in memory_data["preferences"]:
        return f"{key}: {memory_data['preferences'][key]}"
    for fact in reversed(memory_data.get("facts", [])):
        if fact["key"] == key:
            return f"{fact['key']}: {fact['value']}"
    return f"I don't have any memory of '{key}'"


def think_deep(question):
    try:
        messages = [
            {
                "role": "system",
                "content": """You are JARVIS with deep thinking capabilities. Analyze questions from multiple perspectives:
1. Logical/Analytical - facts, data, reasoning
2. Practical/Real-world - how it applies in reality
3. Creative/Innovative - unconventional angles
4. Historical/Contextual - past examples and evolution
5. Future/Implications - long-term effects

Provide thorough, well-reasoned answers. Show your thinking process.""",
            },
            {"role": "user", "content": f"Think deeply about: {question}"},
        ]
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=25,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error in deep thinking: {str(e)}"


def open_url(url, reason=""):
    import subprocess

    if not url.startswith("http"):
        url = "https://" + url
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url])
        return f"Opened: {url}"
    except Exception as e:
        import webbrowser

        webbrowser.open(url)
        return f"Opened: {url}"


def open_app(app_name, song=None):
    global APP_PATTERNS, MUSIC_PLATFORMS

    if song:
        for platform_key in MUSIC_PLATFORMS:
            if platform_key in app_name.lower() or app_name.lower() in platform_key:
                return play_music(song, platform_key)

    app_key = app_name.lower().strip()

    if app_key in APP_PATTERNS:
        app_info = APP_PATTERNS[app_key]
    else:
        for key in APP_PATTERNS:
            if key in app_key or app_key in key:
                app_info = APP_PATTERNS[key]
                break
        else:
            return f"App '{app_name}' not found. Try searching on web."

    win_app = app_info.get("win")
    web_url = app_info.get("web")

    if win_app:
        try:
            subprocess.Popen(win_app)
            return f"Opened {app_name.title()} (Windows App)"
        except:
            pass

    if web_url:
        import subprocess

        if song:
            query = song.replace(" ", "%20")
            search_url = f"{web_url}/search?q={query}"
        else:
            search_url = web_url

        try:
            subprocess.Popen(["cmd", "/c", "start", "", search_url])
        except:
            import webbrowser

            webbrowser.open(search_url)
        return f"Opened {app_name.title()} (Web)"

    return f"Could not open {app_name}"


def play_music(song, platform=None):
    import subprocess
    import time
    import pyautogui

    if not platform:
        platform = "youtube"

    platform_key = platform.lower().strip()

    if platform_key not in MUSIC_PLATFORMS:
        platform_key = "youtube"

    try:
        if platform_key == "youtube":
            import pywhatkit

            print(f"  ▶ Playing '{song}' on YouTube...")
            pywhatkit.playonyt(song)
            return f"▶ Playing '{song}' on YouTube!"

        elif platform_key == "spotify":
            import webbrowser
            import pyautogui as ui
            import time

            webbrowser.open("https://open.spotify.com/")
            time.sleep(7)
            ui.hotkey("ctrl", "shift", "l")
            time.sleep(2)
            ui.write(song)
            time.sleep(1.5)
            ui.leftClick(895, 590)
            return f"▶ Playing '{song}' on Spotify!"

        elif platform_key == "youtube music":
            import urllib.parse

            query = urllib.parse.quote(song)
            url = f"https://music.youtube.com/search?query={query}"
            subprocess.Popen(["cmd", "/c", "start", "", url])
            return f"▶ Opened YouTube Music - search '{song}'. Click on a song to play."

        elif platform_key == "apple music":
            import urllib.parse

            query = urllib.parse.quote(song)
            url = f"https://music.apple.com/in/search?term={query}"
            subprocess.Popen(["cmd", "/c", "start", "", url])
            return f"▶ Opened Apple Music - search '{song}'. Click on a song to play."

        else:
            import urllib.parse

            query = urllib.parse.quote(song)
            url = f"{MUSIC_PLATFORMS.get(platform_key, 'https://open.spotify.com')}/search?q={query}"
            subprocess.Popen(["cmd", "/c", "start", "", url])
            return f"▶ Opened {platform.title()} - search '{song}'. Click on a song to play."

    except Exception as e:
        print(f"  [Error] {e}")
        import urllib.parse

        query = urllib.parse.quote(song)
        url = f"https://www.youtube.com/results?search_query={query}"
        subprocess.Popen(["cmd", "/c", "start", "", url])
        return f"▶ Opened YouTube - search '{song}'. Click on a song to play."


def music_control(action):
    import pyautogui
    import time

    if action == "play" or action == "pause":
        pyautogui.press("space")
        time.sleep(0.3)
        return f"{'▶ Playing' if action == 'play' else '⏸ Paused'}"
    elif action == "next":
        pyautogui.press("right")
        time.sleep(0.3)
        return "⏭ Next track"
    elif action == "previous" or action == "prev":
        pyautogui.press("left")
        time.sleep(0.3)
        return "⏮ Previous track"
    elif action == "volume up":
        pyautogui.press("up")
        time.sleep(0.3)
        return "🔊 Volume up"
    elif action == "volume down":
        pyautogui.press("down")
        time.sleep(0.3)
        return "🔉 Volume down"
    elif action == "mute":
        pyautogui.press("m")
        time.sleep(0.3)
        return "🔇 Muted"
    else:
        return "Unknown control"


def create_folder(folder_name):
    try:
        folder_path = os.path.join(DESKTOP_PATH, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        return f"Created folder: {folder_name} on Desktop"
    except Exception as e:
        return f"Error: {str(e)}"


def create_file(file_name, content=""):
    try:
        file_path = os.path.join(DESKTOP_PATH, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Created file: {file_name} on Desktop"
    except Exception as e:
        return f"Error: {str(e)}"


def delete_item(name, type_):
    try:
        item_path = os.path.join(DESKTOP_PATH, name)
        if type_ == "folder":
            import shutil

            shutil.rmtree(item_path)
        else:
            os.remove(item_path)
        return f"Deleted {type_}: {name}"
    except Exception as e:
        return f"Error: {str(e)}"


def list_desktop():
    try:
        items = os.listdir(DESKTOP_PATH)
        if not items:
            return "Desktop is empty"
        result = "Files on Desktop:\n"
        for item in sorted(items):
            item_path = os.path.join(DESKTOP_PATH, item)
            if os.path.isdir(item_path):
                result += f"  📁 {item}/\n"
            else:
                result += f"  📄 {item}\n"
        return result.strip()
    except Exception as e:
        return f"Error: {str(e)}"


def read_file(file_name):
    try:
        file_path = os.path.join(DESKTOP_PATH, file_name)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"Content of {file_name}:\n{content}"
    except Exception as e:
        return f"Error: {str(e)}"


def execute_tool(tool_name, arguments):
    if tool_name == "open_url":
        return open_url(arguments.get("url"), arguments.get("reason", ""))
    elif tool_name == "open_app":
        return open_app(arguments.get("app_name"), arguments.get("song"))
    elif tool_name == "play_music":
        return play_music(arguments.get("song"), arguments.get("platform"))
    elif tool_name == "create_folder":
        return create_folder(arguments.get("folder_name"))
    elif tool_name == "create_file":
        return create_file(arguments.get("file_name"), arguments.get("content", ""))
    elif tool_name == "delete_item":
        return delete_item(arguments.get("name"), arguments.get("type"))
    elif tool_name == "list_desktop":
        return list_desktop()
    elif tool_name == "read_file":
        return read_file(arguments.get("file_name"))
    elif tool_name == "remember":
        return remember(arguments.get("key"), arguments.get("value"))
    elif tool_name == "recall":
        return recall(arguments.get("key"))
    elif tool_name == "think_deep":
        return think_deep(arguments.get("question"))
    else:
        return f"Unknown tool: {tool_name}"


def detect_voice_file():
    global voice_file_path

    specific_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "voice",
        "JARVIS - Marvel's Iron Man 3 Second Screen Experience - Trailer-enhanced-v2.wav",
    )
    if os.path.exists(specific_file):
        voice_file_path = specific_file
        return voice_file_path

    voice_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice")
    if not os.path.exists(voice_dir):
        return None
    files = glob.glob(os.path.join(voice_dir, "*"))
    audio_files = [
        f for f in files if f.lower().endswith((".wav", ".mp3", ".ogg", ".flac"))
    ]
    if audio_files:
        voice_file_path = audio_files[0]
        return voice_file_path
    return None


def init_speech():
    global speech_enabled
    if not TTS_AVAILABLE:
        return False
    voice = detect_voice_file()
    if voice:
        speech_enabled = True
        return True
    return False


def speak(text):
    global speech_enabled, voice_file_path

    if not speech_enabled:
        print("  [TTS Error] Speech is not enabled/initialized.")
        return

    if not voice_file_path:
        print("  [TTS Error] Voice file not found.")
        return

    try:
        import uuid
        import requests

        pygame.mixer.init()

        with open(voice_file_path, "rb") as f:
            files = {"voice_wav": f}
            data = {"text": text}
            print(f"  [TTS] Generating voice for: {text[:50]}...")
            response = requests.post(
                POCKET_TTS_URL, files=files, data=data, timeout=120
            )
            if response.status_code == 200 and len(response.content) > 100:
                unique_id = uuid.uuid4().hex[:8]
                audio_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    f"temp_speech_{unique_id}.wav",
                )
                with open(audio_path, "wb") as af:
                    af.write(response.content)
                try:
                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                except Exception as e:
                    print(f"  [TTS Audio Error (Pygame)] {e}")
                try:
                    os.remove(audio_path)
                except:
                    pass
            else:
                print(f"  [TTS Server Error] Code: {response.status_code}")
    except Exception as e:
        print(f"  [TTS Error] {e}")


def ask_jarvis(user_input):
    global conversation_history, memory_data
    try:
        conversation_history.append({"role": "user", "content": user_input})

        memory_context = ""
        if memory_data.get("preferences"):
            memory_context = (
                f"\nUser's known preferences: {json.dumps(memory_data['preferences'])}"
            )

        detected_intent = detect_intent(user_input)
        thought = think_step(user_input, detected_intent, memory_context)
        action = decide_action(detected_intent, user_input, memory_context)

        extracted_info = extract_memory(user_input)
        for key, value in extracted_info:
            remember(key, value)

        if action and ("memory_retrieve" in action or "recall" in user_input.lower()):
            import re

            match = re.search(
                r"(?:what is|recall|remember|my)\s+(.+)", user_input.lower()
            )
            if match:
                recall_key = match.group(1).strip()
                if (
                    "name" in recall_key
                    and "preferences" in memory_data
                    and "name" in memory_data["preferences"]
                ):
                    return f"You told me your name is {memory_data['preferences']['name']}."
                recall_result = recall(recall_key)
                if "don't have any memory" not in recall_result.lower():
                    return recall_result

        if action and ("think_deep" in action or "analyze" in user_input.lower()):
            question = user_input
            for phrase in ["think about ", "think deep ", "analyze "]:
                if phrase in user_input.lower():
                    question = user_input.lower().split(phrase)[1]
                    break
            return think_deep(question)

        messages = [
            {
                "role": "system",
                "content": f"""You are JARVIS, an intelligent AI assistant with powerful capabilities.

THINKING: {thought if thought else "Processing request..."}
INTENT: {action}

AVAILABLE TOOLS:
- open_url: Open any website
- open_app: Open apps (Windows or web version in Chrome)
- play_music: Play music on platforms like Spotify, YouTube, Apple Music, Gaana, Jio Saavn, SoundCloud, etc.
- create_folder: Create folder on Desktop
- create_file: Create file on Desktop
- delete_item: Delete file/folder from Desktop
- list_desktop: Show desktop files
- read_file: Read file content
- remember: Store important info in memory
- recall: Retrieve remembered info
- think_deep: Analyze complex questions deeply

USER MEMORY:{memory_context}

When user wants to:
- Open websites/apps → Use open_app (automatically uses web if Windows app unavailable)
- Play music → Use play_music with platform (asks if not specified)
- Remember info → Use remember
- Think deeply → Use think_deep for complex analysis

Be proactive, helpful, and use your tools whenever needed. Keep responses conversational and concise.""",
            }
        ]
        messages.extend(conversation_history[-10:])

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        data = {
            "model": GROQ_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 500,
        }

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]

            if "tool_calls" in message:
                tool_calls = message["tool_calls"]
                messages.append(message)

                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    result_msg = execute_tool(tool_name, arguments)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result_msg,
                        }
                    )

                final_response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": GROQ_MODEL,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                    timeout=20,
                )

                if final_response.status_code == 200:
                    final_result = final_response.json()
                    assistant_reply = final_result["choices"][0]["message"]["content"]
                    conversation_history.append(
                        {"role": "assistant", "content": assistant_reply}
                    )
                    return assistant_reply
            else:
                assistant_reply = message["content"]
                conversation_history.append(
                    {"role": "assistant", "content": assistant_reply}
                )
                return assistant_reply
        else:
            return f"Error: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


def jarvis_print(text):
    print(f"Jarvis > {text}")


def type_text(text, delay=0.03):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def print_banner():
    global speech_enabled, voice_file_path
    print("\033[92m  JARVIS CLI\033[0m")
    print("=" * 60)
    type_text("  Initializing JARVIS System...", 0.01)
    time.sleep(0.1)
    print("  System Online")
    print("  Memory: Loaded" if os.path.exists(MEMORY_FILE) else "  Memory: Empty")

    if TTS_AVAILABLE:
        detected = detect_voice_file()
        if detected:
            speech_enabled = True
            print(f"  TTS: {detected.split('\\')[-1]}")

    if STT_AVAILABLE:
        print("  STT: Ready (type 'listen' to start voice input)")

    print("=" * 60)


def main():
    global speech_enabled, voice_file_path, conversation_history

    load_memory()
    print_banner()

    jarvis_print("Initializing voice modules...")
    time.sleep(0.5)

    jarvis_print("All systems ready!")
    time.sleep(0.3)
    speak("Systems online.")
    time.sleep(0.5)

    print()
    jarvis_print("Welcome Sir! How can I assist you?")
    speak("Welcome Sir! How can I help you?")

    while True:
        try:
            user_input = sys.stdin.readline().strip()
            if not user_input:
                continue

            print(f"\nYou > {user_input}")
            command = user_input.lower()

            if command in ["exit", "quit", "q"]:
                jarvis_print("Shutting down...")
                speak("Goodbye Sir!")
                time.sleep(0.5)
                sys.exit(0)

            elif command in ["help", "h"]:
                print("""
[ COMMANDS ]
  help/h         - Show commands
  status         - System status
  time           - Current time
  date           - Current date
  desktop        - List desktop files
  clear/cls      - Clear screen
  voice          - Toggle TTS voice
  listen         - Start voice listening (continuous)
  stop listen    - Stop voice listening
  clear memory   - Clear JARVIS memory
  exit           - Exit

[ AI CAPABILITIES ]
  • Open apps: "open Spotify", "open Chrome", "open VSCode"
  • Open websites: "open YouTube", "open GitHub"
  • Play music: "play Shape of You" (asks platform)
  • Or: "play Shape of You on Spotify"
  • Create: "create folder Projects", "create file notes.txt"
  • Delete: "delete file old.txt"
  • Remember: "remember my birthday is June 15"
  • Recall: "what's my birthday"
  • Think deeply: "think about artificial intelligence"
""")

            elif command == "status":
                jarvis_print(
                    "All systems operational. AI: Online, Memory: Active, Voice: Ready"
                )

            elif command == "desktop" or command == "list desktop":
                result = list_desktop()
                print(result)

            elif command == "time":
                from datetime import datetime

                jarvis_print(f"Time: {datetime.now().strftime('%I:%M %p')}")

            elif command == "date":
                from datetime import datetime

                jarvis_print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")

            elif command in ["clear", "cls"]:
                os.system("cls" if os.name == "nt" else "clear")
                print_banner()

            elif command == "clear memory":
                memory_data = {"facts": [], "preferences": {}, "conversations": []}
                save_memory()
                jarvis_print("Memory cleared.")

            elif command == "voice":
                if not voice_file_path:
                    detect_voice_file()
                speech_enabled = not speech_enabled
                if speech_enabled:
                    speak("Voice enabled.")
                else:
                    jarvis_print("Voice disabled.")

            elif command in [
                "listen",
                "voice listen",
                "start voice",
                "start listening",
            ]:
                if not STT_AVAILABLE:
                    jarvis_print("STT not available.")
                elif voice_listening:
                    jarvis_print("Already listening. Say something!")
                else:
                    start_voice_listening()

            elif command in ["stop listen", "stop listening", "stop voice"]:
                if voice_listening:
                    stop_voice_listening()
                else:
                    jarvis_print("Not currently listening.")

            elif command in ["pause", "stop"]:
                result = music_control("pause")
                jarvis_print(result)

            elif command in ["resume", "play"]:
                result = music_control("play")
                jarvis_print(result)

            elif command in ["next", "skip"]:
                result = music_control("next")
                jarvis_print(result)

            elif command in ["previous", "prev", "back"]:
                result = music_control("previous")
                jarvis_print(result)

            elif command in ["volume up", "louder"]:
                result = music_control("volume up")
                jarvis_print(result)

            elif command in ["volume down", "quieter"]:
                result = music_control("volume down")
                jarvis_print(result)

            elif command == "mute":
                result = music_control("mute")
                jarvis_print(result)

            elif user_input.lower().startswith("play ") or "play" in user_input.lower():
                import re

                if "random" in user_input.lower():
                    import random

                    random_songs = [
                        "Shape of You",
                        "Despacito",
                        "Uptown Funk",
                        "See You Again",
                        "Thinking Out Loud",
                        "Perfect",
                        "Senorita",
                        "Believer",
                    ]
                    song = random.choice(random_songs)
                    platform = "youtube"
                    jarvis_print(f"Playing random: '{song}' on {platform}...")
                    result = play_music(song, platform)
                    jarvis_print(result)
                    continue

                match = re.match(
                    r"play\s+(.+?)\s+on\s+(\w+)", user_input, re.IGNORECASE
                )
                if match:
                    song = match.group(1).strip()
                    platform = match.group(2).strip()
                else:
                    parts = re.split(r"\s+on\s+", user_input, flags=re.IGNORECASE)
                    if len(parts) == 2:
                        song = parts[0].replace("play", "").strip()
                        platform = parts[1].strip()
                    elif "play music" in user_input.lower():
                        song = user_input.lower().replace("play music", "").strip()
                        if not song:
                            platform = "youtube"
                            song = "trending songs"
                        else:
                            platform = "youtube"
                    else:
                        song_match = re.search(
                            r"play\s+(.+)", user_input, re.IGNORECASE
                        )
                        if song_match:
                            song = song_match.group(1).strip()
                            platform = "youtube"
                        else:
                            jarvis_print(
                                "Use: play <song> or play <song> on <platform>"
                            )
                            continue

                if not platform or platform == "music":
                    platform = "youtube"

                jarvis_print(f"Playing '{song}' on {platform}...")
                result = play_music(song, platform)
                jarvis_print(result)
                continue

            else:
                jarvis_print("Thinking...")
                response = ask_jarvis(user_input)
                jarvis_print(response)
                if (
                    speech_enabled
                    and voice_file_path
                    and "quiet" not in user_input.lower()
                    and "fast" not in user_input.lower()
                ):
                    speak(response)

        except KeyboardInterrupt:
            speak("Goodbye Sir!")
            time.sleep(0.5)
            print("\n  Jarvis shutting down...")
            sys.exit(0)
        except Exception as e:
            print(f"  Error: {str(e)}")


if __name__ == "__main__":
    main()
