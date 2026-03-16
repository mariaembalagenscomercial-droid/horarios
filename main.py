from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from datetime import datetime
import pytz

app = FastAPI()

# URLs das imagens no Cloudinary (com cache busting via versão)
URL_ABERTA = 'https://res.cloudinary.com/dpafw5oik/image/upload/v2/loja_aberta.png'
URL_FECHADA = 'https://res.cloudinary.com/dpafw5oik/image/upload/v2/loja_fechada.png'

def esta_aberto():
    """
    Horários de funcionamento Maria Embalagens:
    - Segunda:  22:00 — 23:59
    - Terça:    00:00 — 10:00
    - Quarta:   05:00 — 10:00 | 22:00 — 23:59
    - Quinta:   00:00 — 10:00
    - Sexta:    05:00 — 10:00 | 22:00 — 23:59
    - Sábado:   00:00 — 10:00
    - Domingo:  FECHADO
    """
    tz = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(tz)

    dia = agora.weekday()  # 0=segunda, 1=terça, ..., 6=domingo
    hora = agora.hour
    minuto = agora.minute
    tempo = hora * 60 + minuto  # em minutos

    # Segunda (0): 22:00 — 23:59
    if dia == 0:
        return tempo >= 22 * 60

    # Terça (1): 00:00 — 10:00
    if dia == 1:
        return tempo < 10 * 60

    # Quarta (2): 05:00 — 10:00 | 22:00 — 23:59
    if dia == 2:
        return (5 * 60 <= tempo < 10 * 60) or (tempo >= 22 * 60)

    # Quinta (3): 00:00 — 10:00
    if dia == 3:
        return tempo < 10 * 60

    # Sexta (4): 05:00 — 10:00 | 22:00 — 23:59
    if dia == 4:
        return (5 * 60 <= tempo < 10 * 60) or (tempo >= 22 * 60)

    # Sábado (5): 00:00 — 10:00
    if dia == 5:
        return tempo < 10 * 60

    # Domingo (6): Fechado
    return False

@app.get("/status-widget.png")
async def get_status_widget():
    """Redireciona para a imagem correta baseado no horário de Brasília"""
    url = URL_ABERTA if esta_aberto() else URL_FECHADA
    return RedirectResponse(url=url, status_code=302)

@app.get("/")
async def root():
    tz = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(tz)
    aberto = esta_aberto()
    return {
        "loja": "Maria Embalagens",
        "horario_brasilia": agora.strftime("%d/%m/%Y %H:%M"),
        "status": "ABERTA" if aberto else "FECHADA",
        "widget_url": "/status-widget.png"
    }
