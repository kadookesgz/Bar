# TPV Hostelería — V2 híbrida

TPV propio para hostelería, inspirado funcionalmente en las soluciones de HIOPOS, con arquitectura multiempresa, PWA multiplataforma y diseño local-first.

La rama `v2-hybrid-architecture` desarrolla la V2. La versión anterior de pedidos QR permanece intacta en `main`.

## Funcionalidades ya incorporadas en esta base de desarrollo

- Primera instalación guiada: crea empresa, establecimiento y usuario propietario.
- Autenticación con JWT y contraseñas Argon2.
- Aislamiento de consultas por empresa y establecimiento.
- Catálogo: familias, productos, precios, IVA, alérgenos y grupos de modificadores/suplementos.
- Sala: zonas, mesas y enlaces QR con token revocable.
- TPV: creación de comandas, cuentas abiertas por mesa, modificadores, canales local/recogida/delivery, división de cuentas y descuentos.
- Caja: apertura/cierre de turno, arqueo, pagos parciales, varios métodos y registro de reembolsos.
- Cocina: cola KDS y estados de preparación; consumo de ingredientes al terminar platos con receta.
- Pedidos QR: QR PNG imprimible por mesa, carta móvil, selección de productos y envío directo a cocina.
- Reservas: agenda básica y estados.
- Almacén: artículos, stock, movimientos y alertas de mínimo.
- Compras: proveedores, pedidos y recepción que actualiza existencias.
- Escandallos: recetas, componentes y cálculo inicial de coste.
- Menús/combos: estructura de menús con productos, grupos y suplementos.
- Promociones: descuentos fijos/porcentuales y aplicación por código.
- Tarifas: listas de precios vinculables a zonas (la aplicación automática en ventas queda pendiente).
- Empleados: usuarios, perfiles y permisos iniciales; planificación de turnos por API.
- Clientes: fichas y puntos de fidelización.
- Informes: ventas diarias, ticket medio, productos principales y formas de pago.
- Base de datos PostgreSQL y migraciones Alembic.
- PWA responsive para pantallas Windows, tablets y Android; vista de ticket imprimible desde navegador.\n- Cola local outbox con eventos de ventas, cobros, reservas y movimientos de stock, preparada para sincronización futura.

## Arranque en Windows

Requisitos: Docker Desktop con Docker Compose y virtualización habilitada.

1. Descarga la rama `v2-hybrid-architecture`.
2. En PowerShell, desde la carpeta del proyecto:

```powershell
Copy-Item .env.example .env
notepad .env
```

3. Sustituye `POSTGRES_PASSWORD` y `JWT_SECRET` por dos secretos diferentes. Puedes generar cada uno con:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

4. Arranca el sistema:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
```

5. Abre http://localhost:8000. La primera pantalla permite crear empresa, local y usuario administrador.
6. Documentación de la API: http://localhost:8000/docs

## Perfiles iniciales

- owner: propietario.
- manager: encargado.
- waiter: camarero.
- kitchen: cocina.
- cashier: caja.

Los permisos están en una primera iteración y deben revisarse antes de desplegar a clientes.

## Arquitectura y límites actuales

- La venta y la base de datos se ejecutan en el servidor local PostgreSQL.
- La PWA se sirve desde el servidor local; Internet no es necesario para el acceso en la LAN.
- La cola local de sincronización ya registra eventos, pero el sincronizador local-nube y la consola SaaS central todavía no están implementados.
- La aplicación todavía no debe exponerse directamente a Internet.
- No hay integración real con datáfonos, CashDro, impresoras ESC/POS ni plataformas externas de delivery.
- La impresión térmica automática está pendiente; por ahora se puede usar impresión del navegador.
- Facturación fiscal, VERI*FACTU, rectificativas y registros de eventos están pendientes de análisis e implementación normativa. No se debe emitir como software fiscalmente conforme hasta completar esa fase y validarla.
- Las funciones de contabilidad, conciliación, B2B, campañas de marketing, página web y asistentes IA quedan en el roadmap.

## Estado de validación

Los archivos están publicados en GitHub, pero esta entrega no incluye una prueba de ejecución de extremo a extremo en un equipo Windows ni pruebas de concurrencia/aislamiento. Debe probarse en entorno de desarrollo antes de utilizarse con ventas reales.

## Siguiente fase

Consultar `docs/ROADMAP_V2.md` para el plan de cierre de brechas y la matriz de funcionalidades.
