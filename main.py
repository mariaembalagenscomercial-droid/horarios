from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from datetime import datetime
import pytz
import httpx
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# URLs das imagens no Cloudinary (formato WebP otimizado)
URL_ABERTA = 'https://res.cloudinary.com/dpafw5oik/image/upload/v2/loja_aberta.webp'
URL_FECHADA = 'https://res.cloudinary.com/dpafw5oik/image/upload/v2/loja_fechada.webp'

# Timezone de Brasilia (carregado uma vez na inicializacao)
TZ_BRASILIA = pytz.timezone('America/Sao_Paulo')

# Configuracao do monitoramento
LOJA_URL = 'https://mariaembalagens.com.br'
WHATSAPP_BUTTON_ID = 'whatsapp-cart-button'
EMAIL_ALERTA = os.environ.get('EMAIL_ALERTA', 'mariaembalagenscomercial@gmail.com')
EMAIL_SENHA = os.environ.get('EMAIL_SENHA', '')
ULTIMO_ALERTA = None


def esta_aberto():
    agora = datetime.now(TZ_BRASILIA)
    dia = agora.weekday()
    tempo = agora.hour * 60 + agora.minute

    if dia == 0:
        return tempo >= 22 * 60
    if dia == 1:
        return tempo < 10 * 60
    if dia == 2:
        return (5 * 60 <= tempo < 10 * 60) or (tempo >= 22 * 60)
    if dia == 3:
        return tempo < 10 * 60
    if dia == 4:
        return (5 * 60 <= tempo < 10 * 60) or (tempo >= 22 * 60)
    if dia == 5:
        return tempo < 10 * 60
    return False


async def verificar_botao_whatsapp():
    """Verifica se o botao de WhatsApp esta presente no carrinho da loja."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(f'{LOJA_URL}/')
            html_principal = resp.text

            botao_presente = (
                WHATSAPP_BUTTON_ID in html_principal or
                'Comprar pelo WhatsApp' in html_principal or
                'whatsapp-cart-button' in html_principal
            )

            resp_cart = await client.get(f'{LOJA_URL}/checkout/')
            html_cart = resp_cart.text

            botao_no_cart = (
                WHATSAPP_BUTTON_ID in html_cart or
                'Comprar pelo WhatsApp' in html_cart or
                'whatsapp-cart-button' in html_cart or
                'wa.me' in html_cart
            )

            return {
                'botao_na_home': botao_presente,
                'botao_no_cart': botao_no_cart,
                'status_home': resp.status_code,
                'status_cart': resp_cart.status_code,
                'presente': botao_presente or botao_no_cart
            }
    except Exception as e:
        logger.error(f"Erro ao verificar botao: {e}")
        return {
            'botao_na_home': False,
            'botao_no_cart': False,
            'status_home': 0,
            'status_cart': 0,
            'presente': False,
            'erro': str(e)
        }


def enviar_alerta_email(resultado):
    """Envia email de alerta quando o botao WhatsApp nao e encontrado."""
    global ULTIMO_ALERTA

    agora = datetime.now(TZ_BRASILIA)
    if ULTIMO_ALERTA and (agora - ULTIMO_ALERTA).total_seconds() < 21600:
        logger.info("Alerta ja enviado recentemente, ignorando.")
        return False

    if not EMAIL_SENHA:
        logger.warning("EMAIL_SENHA nao configurada. Alerta nao enviado.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ALERTA
        msg['To'] = EMAIL_ALERTA
        msg['Subject'] = 'ALERTA: Botao WhatsApp sumiu da loja!'

        corpo = '<h2 style="color:#e74c3c;">Alerta - Botao WhatsApp Nao Encontrado</h2>'
        corpo += '<p>O monitoramento automatico detectou que o botao de compra pelo WhatsApp nao esta mais presente na loja.</p>'
        corpo += '<p>Acesse o FTP da Nuvemshop e reenvie o cart-button.tpl em /snippets/cart/</p>'

        msg.attach(MIMEText(corpo, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_ALERTA, EMAIL_SENHA)
            server.send_message(msg)

        ULTIMO_ALERTA = agora
        logger.info("Alerta enviado com sucesso!")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar alerta: {e}")
        return False


# ============ ENDPOINTS ORIGINAIS ============

@app.get("/status-widget.png")
async def get_status_widget():
    url = URL_ABERTA if esta_aberto() else URL_FECHADA
    return RedirectResponse(
        url=url,
        status_code=302,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/")
async def root():
    agora = datetime.now(TZ_BRASILIA)
    aberto = esta_aberto()
    return {
        "loja": "Maria Embalagens",
        "horario_brasilia": agora.strftime("%d/%m/%Y %H:%M"),
        "status": "ABERTA" if aberto else "FECHADA",
        "widget_url": "/status-widget.png"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ============ ENDPOINTS DE MONITORAMENTO ============

@app.get("/monitor")
async def monitor():
    resultado = await verificar_botao_whatsapp()
    agora = datetime.now(TZ_BRASILIA)

    if not resultado.get('presente'):
        alerta_enviado = enviar_alerta_email(resultado)
        resultado['alerta_enviado'] = alerta_enviado
    else:
        resultado['alerta_enviado'] = False

    resultado['verificado_em'] = agora.strftime('%d/%m/%Y %H:%M')
    return resultado


@app.get("/monitor/check")
async def monitor_check():
    resultado = await verificar_botao_whatsapp()
    agora = datetime.now(TZ_BRASILIA)

    status = "OK" if resultado.get('presente') else "ALERTA"

    if not resultado.get('presente'):
        enviar_alerta_email(resultado)

    return {
        "status": status,
        "botao_presente": resultado.get('presente', False),
        "verificado_em": agora.strftime('%d/%m/%Y %H:%M')
    }
