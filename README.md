# Bar de Tapas QR — versión 1.1

Aplicación web para pedidos desde QR por mesa, panel de caja y cocina con actualización automática, datos persistentes en SQLite, carta editable y tickets imprimibles desde el navegador. Incluye cuentas abiertas por mesa con historial y solicitud de cuenta. No integra Bizum.

## Instalación en Windows
1. Instala Python 3.10 o posterior.
2. Descarga el repositorio (Code → Download ZIP) y descomprímelo.
3. Ejecuta `run_windows.bat` para instalar dependencias y arrancar.
4. Edita `.env`: cambia `ADMIN_PASSWORD` y establece `BASE_URL=http://IP_DEL_PC:8000` (por ejemplo `http://192.168.1.50:8000`). Reinicia el programa.

## Linux / Raspberry Pi
```bash
chmod +x install_linux.sh
./install_linux.sh
# Edita .env: cambia contraseña y BASE_URL
set -a; source .env; set +a
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Direcciones
- Carta: `http://IP_DEL_EQUIPO:8000/mesa/1`
- Caja: `http://IP_DEL_EQUIPO:8000/caja`
- Cocina: `http://IP_DEL_EQUIPO:8000/cocina`
- Administración: `http://IP_DEL_EQUIPO:8000/admin`
- Diagnóstico: `http://IP_DEL_EQUIPO:8000/health`

Caja, cocina y administración requieren autenticación HTTP Basic. Los QR se generan en Administración. El teléfono debe poder acceder a la IP del servidor por la Wi-Fi del local; no uses `127.0.0.1` para QR reales.

## Funciones
- Carta editable, categorías, precios y disponibilidad.
- QR únicos por mesa.
- Pedidos guardados en SQLite y paneles de caja/cocina con actualización automática.
- Estados: nuevo, aceptado, en preparación, listo y servido.
- Marcar cobro e imprimir tickets desde el navegador.
- Cuentas abiertas por mesa: total acumulado, historial, estados y solicitud de cuenta.
- Para compartir la cuenta entre móviles, el cliente introduce el código de cuatro cifras que muestra Caja o que se facilitó al abrir la cuenta.
- Caja puede cerrar la cuenta; la siguiente visita genera una cuenta nueva.
- Exportación de datos JSON desde Administración.

## Importante
- Los productos de ejemplo son ficticios; verifica precios y alérgenos.
- No incluye Bizum, pago online, TPV ni facturación fiscal.
- La impresión se realiza mediante el diálogo del navegador; la impresión automática requiere integración específica con la impresora.
- Es una versión inicial para un local. No expongas el puerto 8000 directamente a Internet. Para uso real, usa HTTPS, contraseña fuerte, copias de seguridad y controles antiabuso.
- La base de datos `bar_tapas.db` es local y no debe subirse al repositorio.
