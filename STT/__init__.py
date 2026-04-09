import speech_recognition as sr
import os

class SpeechToText:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = False
    
    def calibrate_microphone(self, duration=2):
        """Calibrate microphone for ambient noise."""
        print("  Calibrating microphone...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=duration)
        print("  Microphone calibrated.")
    
    def listen(self, timeout=5, phrase_time_limit=10):
        """Listen for speech and convert to text."""
        with self.microphone as source:
            print("  Listening...")
            try:
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout, 
                    phrase_time_limit=phrase_time_limit
                )
                return audio
            except sr.WaitTimeoutError:
                return None
    
    def recognize_google(self, audio, language="en-US"):
        """Recognize speech using Google Speech Recognition."""
        try:
            text = self.recognizer.recognize_google(audio, language=language)
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            return f"API Error: {str(e)}"
    
    def recognize_sphinx(self, audio):
        """Recognize speech using CMU Sphinx (offline)."""
        try:
            text = self.recognizer.recognize_sphinx(audio)
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            return f"Sphinx Error: {str(e)}"
    
    def listen_and_recognize(self, timeout=5, phrase_time_limit=10, method="google", language="en-US"):
        """Complete STT pipeline: listen and recognize."""
        audio = self.listen(timeout=timeout, phrase_time_limit=phrase_time_limit)
        
        if audio is None:
            return None
        
        if method == "sphinx":
            return self.recognize_sphinx(audio)
        else:
            return self.recognize_google(audio, language)
    
    def listen_continuous(self, callback, timeout=5, phrase_time_limit=10):
        """Continuous listening with callback function."""
        def audio_callback(recognizer, audio):
            try:
                text = recognizer.recognize_google(audio)
                callback(text)
            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                print(f"API Error: {str(e)}")
        
        stop_listening = self.recognizer.listen_in_background(
            self.microphone, 
            audio_callback
        )
        return stop_listening


_stt_instance = None

def get_stt_instance():
    """Get or create STT singleton instance."""
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = SpeechToText()
    return _stt_instance

def initialize_stt():
    """Initialize and calibrate the STT module."""
    stt = get_stt_instance()
    stt.calibrate_microphone()
    return stt

def recognize_speech(timeout=5, phrase_time_limit=10, language="en-US"):
    """Quick function to recognize speech."""
    stt = get_stt_instance()
    return stt.listen_and_recognize(
        timeout=timeout, 
        phrase_time_limit=phrase_time_limit,
        language=language
    )
