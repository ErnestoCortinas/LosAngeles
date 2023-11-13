import os
import smtplib
from flask_mail import Mail, Message
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, current_app
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
import pytz
from flask_sse import sse
from apscheduler.jobstores.base import JobLookupError
from flask import redirect, request
from flask import render_template_string
from decouple import config

app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"  # Asegúrate de que Redis esté en ejecución y configurado
app.config['MAIL_SERVER'] = 'tu_servidor_smtp.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = config('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = config('MAIL_PASSWORD')

mail = Mail(app)


utc = pytz.utc

now = datetime.now(utc)

UPLOAD_FOLDER = "pdf_manager/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Define una lista para almacenar los datos de los recordatorios
recordatorios_programados = []

# Función para enviar correos
def enviar_correo(asunto, destinatario, cuerpo):
   msg = Message("Asunto del Correo", sender="tu_direccion_de_correo@gmail.com", recipients=["destinatario@example.com"])
   msg.body = "Contenido del correo"
    
   mail.send(msg)
    
   return "Correo enviado!"

# Definir la función recordatorio
def recordatorio(asunto, segundos_hasta_alarma, destinatario, app):
    with app.app_context():
        mensaje = f"¡Es hora de tu recordatorio! Asunto: {asunto}. Faltan {segundos_hasta_alarma} segundos para la alarma."
        current_app.extensions['sse'].publish({"message": mensaje}, type="notification")

        # Envía la alerta por correo
        enviar_correo(asunto, destinatario, mensaje)

@app.route('/')
def index():
    return render_template('subir.html')

scheduler = BackgroundScheduler()
scheduler.start()  # Inicia el planificador

@app.route('/subir', methods=['GET', 'POST'])
def subir_archivo():
    if request.method == 'POST':
        archivo = request.files['archivo']
        seccion = request.form['seccion']
        if archivo:
            carpeta_seccion = os.path.join(app.config['UPLOAD_FOLDER'], seccion)
            if not os.path.exists(carpeta_seccion):
                os.makedirs(carpeta_seccion)

            archivo.save(os.path.join(carpeta_seccion, archivo.filename))
            return redirect(url_for('subir_archivo'))

    return render_template('subir.html')

@app.route('/ver/<seccion>')
def ver_archivos(seccion):
    archivos = os.listdir(os.path.join(app.config['UPLOAD_FOLDER'], seccion))
    return render_template('ver_archivos.html', seccion=seccion, archivos=archivos)

@app.route('/descargar/<seccion>/<archivo>')
def descargar(seccion, archivo):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], seccion), archivo)

@app.route('/programar-recordatorio', methods=['POST'])
def programar_recordatorio():
    asunto = request.form['asunto']
    destinatario = request.form['destinatario']
    fecha = request.form['fecha']
    hora = request.form['hora']
    fecha_hora_recordatorio = f"{fecha} {hora}"
    fecha_hora_recordatorio = datetime.strptime(fecha_hora_recordatorio, "%Y-%m-%d %H:%M")

    segundos_hasta_alarma = int((fecha_hora_recordatorio - datetime.now()).total_seconds())

    # Almacena los datos en la lista de recordatorios programados
    recordatorios_programados.append({
        'asunto': asunto,
        'segundos_hasta_alarma': segundos_hasta_alarma,
        'destinatario': destinatario,
    })

    # Programa el recordatorio y envía la alerta por correo
    scheduler.add_job(
        lambda: recordatorio(asunto, segundos_hasta_alarma, destinatario),
        DateTrigger(run_date=fecha_hora_recordatorio)
    )

    # Define el regreso a la página anterior en 1.5 segundos
    return render_template_string("""
    <html>
    <head>
    <meta http-equiv="refresh" content="1.5;url={{ referrer }}" />
    </head>
    <body>
    Recordatorio programado con éxito. Redirigiendo...
    </body>
    </html>
    """, referrer=request.referrer)

@app.route('/ver-recordatorios')
def ver_recordatorios():
    return render_template('ver_recordatorios.html', recordatorios=recordatorios_programados)

@app.route('/eliminar-recordatorio/<job_id>')
def eliminar_recordatorio(job_id):
    try:
        scheduler.remove_job(job_id)
        return "Recordatorio eliminado con éxito"
    except JobLookupError:
        return "El recordatorio no se pudo encontrar o ya ha sido eliminado"

@app.route('/nuevo-recordatorio')
def nuevo_recordatorio():
    return render_template('programar_recordatorio.html')

@app.route('/mostrar-recordatorios')
def mostrar_recordatorios():
    recordatorios = scheduler.get_jobs()
    return render_template('ver_recordatorios.html', recordatorios=recordatorios)

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.register_blueprint(sse, url_prefix='/stream')  # Registra la extensión de SSE
    app.run(debug=True)
