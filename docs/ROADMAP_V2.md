# Roadmap V2 — TPV Hostelería

## Fase 0 — Base técnica (en curso)
- [x] Crear rama independiente `v2-hybrid-architecture`.
- [x] Definir arquitectura multiempresa local-first.
- [x] Definir modelo de sincronización outbox/idempotencia.
- [ ] Crear monorepo frontend/backend y entorno Docker.
- [ ] Añadir CI, lint, pruebas y migraciones.
- [ ] Definir configuración por entorno y secretos.

## Fase 1 — Núcleo TPV local
- [ ] Alta inicial de empresa y establecimiento.
- [ ] Usuarios, roles y permisos.
- [ ] Familias, productos, modificadores, precios e impuestos.
- [ ] Plano de sala, zonas y mesas.
- [ ] Apertura de cuenta y gestión de comandas.
- [ ] División/unión de cuentas.
- [ ] Estados de pedido y envío a estaciones de cocina.
- [ ] Caja: apertura, movimientos, cobros, devoluciones y cierre.
- [ ] Registro de auditoría.
- [ ] Panel de salud y copia/restauración local.

## Fase 2 — Experiencia operativa
- [ ] PWA táctil Windows/Android.
- [ ] Pantalla KDS en tiempo real.
- [ ] QR por mesa y carta pública.
- [ ] Pedidos desde QR vinculados a una sesión de mesa.
- [ ] Impresión térmica mediante adaptadores.
- [ ] Funcionamiento probado sin Internet durante una jornada y recuperación posterior.

## Fase 3 — Sincronización y SaaS
- [ ] API central y registro de empresas.
- [ ] Outbox/inbox, reintentos e idempotencia.
- [ ] Resolución de conflictos documentada.
- [ ] Consola de administración SaaS.
- [ ] Licencias y límites por plan.
- [ ] Observabilidad y copias de seguridad cifradas.

## Fase 4 — Gestión avanzada
- [ ] Inventario y movimientos de stock.
- [ ] Recetas, escandallos, mermas y alérgenos.
- [ ] Proveedores, pedidos de compra y recepción.
- [ ] Clientes e historial.
- [ ] Informes de ventas, márgenes y rendimiento.
- [ ] Multiestablecimiento.

## Fase 5 — Facturación y periféricos
- [ ] Análisis normativo de facturación aplicable.
- [ ] Facturas simplificadas/completas y rectificativas.
- [ ] Integración fiscal conforme a requisitos aplicables y pruebas.
- [ ] Adaptadores ESC/POS, cajón, visor y lectores.
- [ ] Pruebas de hardware y certificación/validación que corresponda.

## Criterios de aceptación de la primera versión utilizable

- Crear un local y usuarios con permisos distintos.
- Crear productos, familias, modificadores y precios.
- Abrir una mesa, añadir artículos y enviarlos a cocina.
- Cobrar total o parcialmente y cerrar la cuenta.
- Registrar apertura/cierre de caja y arqueo.
- Seguir operando si se desconecta Internet.
- Sincronizar al volver la conexión sin duplicar ventas ni pagos.
- Demostrar que un usuario de una empresa no puede consultar datos de otra.
- Restaurar una copia de seguridad en un entorno limpio.
