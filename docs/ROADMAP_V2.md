# Roadmap V2 — TPV Hostelería inspirado en HIOPOS

El alcance toma como referencia las categorías públicas de HIOPOS para hostelería: TPV, comanderos, QR, reservas, cocina, pedidos omnicanal, stock, ERP, empleados, fidelización, informes y gestión centralizada. No se copia código, marca ni interfaz propietaria.

## Implementado en la rama de desarrollo
- [x] Arquitectura multiempresa y multiestablecimiento en el modelo de datos.
- [x] Primera instalación, empresa, local y propietario.
- [x] Inicio de sesión JWT y hash Argon2.
- [x] Catálogo, familias, precios, IVA y alérgenos.
- [x] Zonas, mesas y gestión inicial de varios establecimientos.
- [x] Comandas, líneas de pedido y modificadores/suplementos asociados a productos.
- [x] Cambio de mesa, descuento manual y división básica de cuenta por líneas mediante API.
- [x] Cobros parciales y varios métodos de pago.
- [x] Apertura/cierre de caja y arqueo.
- [x] KDS básico con estados y eventos.
- [x] QR por mesa con token revocable, PNG local imprimible, carta y pedido móvil.
- [x] Reservas básicas.
- [x] Almacén, proveedores, compras y recepción.
- [x] Recetas/escandallos y consumo automático de ingredientes al completar platos.
- [x] Menús/combos y suplementos en modelo/API.
- [x] Promociones y códigos de descuento.
- [x] Listas de precios por zona en modelo/API.
- [x] Empleados, perfiles, planificación básica de turnos y alta de establecimientos adicionales.
- [x] Clientes y puntos de fidelización.
- [x] Informe diario de ventas y productos.
- [x] PWA responsive y Docker Compose con PostgreSQL/Alembic.

## Fase 1 — Consolidar el núcleo del TPV
- [ ] Pruebas automatizadas de todos los flujos y aislamiento multiempresa.
- [ ] Concurrencia: numeración de tickets, bloqueo de cuentas, idempotencia de cobros.
- [ ] Añadir productos a cuentas ya abiertas desde la pantalla táctil del TPV (API disponible).
- [x] Integrar modificadores y suplementos en la toma de pedido y validar grupos obligatorios.\n- [ ] Completar formatos/variantes de producto y selección visual avanzada de modificadores.
- [ ] Aplicar automáticamente tarifas por zona y reglas de precios.
- [ ] Completar devoluciones, anulaciones, reembolsos y trazabilidad de caja.
- [ ] Añadir impresora de tickets, impresoras por estación y cajón portamonedas.
- [ ] Mejorar plano de sala con edición visual y estados de mesa.
- [ ] KDS con prioridad, tiempos, agrupación por estación y avisos.
- [ ] Pantalla de comandero móvil para camareros.
- [ ] Mejorar UI de reservas, empleados, clientes, compras, recetas y promociones.

## Fase 2 — Operativa omnicanal
- [ ] Pedidos online para recoger y delivery.
- [ ] Gestión de direcciones, franjas de entrega y tarifas de reparto.
- [ ] Integraciones con agregadores externos mediante APIs oficiales.
- [ ] Portal web del establecimiento con carta, reservas y promociones.
- [ ] Autoservicio/kiosco y carta multidioma.
- [ ] Pago online opcional y conexión con terminales de pago (según proveedor).
- [ ] Confirmaciones y recordatorios de reservas.
- [ ] Lista de espera y asignación inteligente de mesas.

## Fase 3 — ERP de hostelería
- [ ] Inventario avanzado, inventarios físicos, traspasos y mermas.
- [ ] Escandallos con coste por rendimiento, formatos y subrecetas.
- [ ] Previsión de compra y alertas de reposición.
- [ ] Gestión completa de proveedores y albaranes.
- [ ] Producción, lotes, caducidades y trazabilidad alimentaria.
- [ ] Costes, márgenes, rentabilidad y contabilidad/exports.
- [ ] Gestión de turnos, fichajes, vacaciones y costes laborales.
- [ ] CRM avanzado, segmentación, campañas y promociones automáticas.
- [ ] B2B: pedidos y tarifas de clientes profesionales.

## Fase 4 — SaaS híbrido multiempresa
- [ ] Servicio cloud de empresas, locales, licencias y planes.
- [ ] Sincronización local-nube mediante outbox/inbox, reintentos e idempotencia.
- [ ] Resolución de conflictos y registro de auditoría.
- [ ] Consola central para gestionar múltiples locales y cadenas.
- [ ] Informes consolidados y comparación entre establecimientos.
- [ ] Backups cifrados, restauración probada, observabilidad y alertas.
- [ ] Gestión de dispositivos y configuración centralizada.
- [ ] Portal de soporte y diagnóstico remoto con consentimiento.

## Fase 5 — Fiscalidad y cumplimiento
- [ ] Análisis de obligaciones aplicables a cada modalidad de facturación.
- [ ] Facturas simplificadas/completas, rectificativas y series.
- [ ] Integridad, encadenamiento, registros de eventos y exportación.
- [ ] Implementación VERI*FACTU o modalidad aplicable conforme al calendario y normativa vigente.
- [ ] Pruebas técnicas, auditoría y validación por asesoría especializada.
- [ ] Protección de datos, conservación y derechos de clientes.

## Fase 6 — Funciones avanzadas
- [ ] Página web editable por bloques.
- [ ] IA para digitalizar facturas/albaranes y sugerir pedidos (con revisión humana).
- [ ] Voicebot/reservas asistidas, siempre con confirmación humana.
- [ ] Analítica avanzada y previsión de demanda.
- [ ] Gestión multi-país, idiomas, monedas e impuestos locales.

## Criterios para considerar la V2 lista para piloto

- Operar una jornada completa sin Internet en la LAN.
- No perder comandas ni duplicar cobros al reconectar.
- Separación de datos entre dos empresas probada automáticamente.
- Cobros parciales, división de cuentas, devoluciones y arqueo conciliados.
- Impresión fiable en los periféricos elegidos.
- Restaurar un backup en un servidor limpio.
- Revisión legal/fiscal antes de facturar a clientes reales.
