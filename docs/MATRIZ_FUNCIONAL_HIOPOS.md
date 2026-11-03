# Matriz de funcionalidades — referencia HIOPOS

Esta matriz toma como referencia las capacidades que HIOPOS publica para hostelería: TPV, comanderos, QR, sala, menús/combos, escandallos, fidelización, reservas, pedidos omnicanal, cocina, stock, web, pagos, empleados, promociones, contabilidad y analítica. HIOPOS también ha anunciado en 2026 digitalización documental con IA, trazabilidad por lotes, KDS y gestión inteligente de reservas/Voicebot.

La matriz describe el estado real de nuestra rama `v2-hybrid-architecture`; no implica equivalencia comercial ni certificación.

| Área de referencia | Estado de nuestro TPV |
|---|---|
| TPV táctil | Parcial: catálogo, cuentas, mesas, comanda y pagos parciales |
| Comandero móvil | Parcial: PWA adaptable; falta una experiencia específica optimizada para camareros |
| QR de mesa | Básico funcional: QR imprimible, carta y pedido a cocina; falta pago online |
| Sala y terrazas | Básico: zonas, mesas, ocupación derivada de cuentas; falta editor visual de plano |
| Menús y combos | API y modelos para menús, productos, grupos y suplementos; falta editor visual |
| Formatos y variantes | Pendiente: formatos de compra/venta, unidades y conversión |
| Modificadores | API y selección básica en TPV con suplemento |
| Escandallos | Básico funcional: recetas, coste inicial y consumo de ingredientes al completar plato |
| Reservas | Básico funcional: alta, agenda y estados; falta autoasignación, lista de espera, recordatorios y no-show |
| Pedidos online | Parcial: canales local, recogida y delivery desde TPV; falta tienda pública completa |
| Plataformas externas | Pendiente: conectores oficiales de agregadores |
| Cocina/KDS | Básico funcional: cola y estados; faltan estaciones visuales, prioridades, tiempos e impresión por estación |
| Stock/almacén | Básico funcional: artículos, niveles, movimientos y alerta de mínimo |
| Compras | Básico funcional: proveedores, pedido y recepción de stock; faltan albaranes, facturas y reposición sugerida |
| Traspasos entre locales | Pendiente |
| Lotes y caducidades | Pendiente |
| Clientes/CRM | Básico: ficha e historial mínimo; faltan segmentación y perfil 360 |
| Fidelización | Básico: puntos manuales; faltan reglas automáticas, recompensas y campañas |
| Promociones | Básico: descuento fijo/porcentual y código; faltan 2x1, 3x2, happy hour y reglas combinadas |
| Empleados | Básico: usuarios, perfiles y turnos programados; falta fichaje, ausencias y coste laboral |
| Caja y pagos | Básico: turnos, arqueo, cobros parciales, reembolsos parciales y ticket imprimible desde navegador; faltan integración PINPAD, CashDro y pagos QR |
| Impresión/periféricos | Ticket HTML imprimible; faltan ESC/POS, impresoras por estación, visor y cajón |
| Informes/Analytics | Básico: informe diario; faltan paneles avanzados y consolidación multi-local |
| Contabilidad/finanzas | Pendiente |
| Facturación fiscal | Pendiente de análisis e implementación normativa; no emitir como sistema fiscal conforme |
| B2B | Pendiente |
| Web del establecimiento | Pendiente |
| Kiosco/autoservicio | Pendiente |
| Multiempresa/multilocal | Modelo y API inicial para empresa/locales; SaaS central y administración comercial pendientes |
| Híbrido local-nube | Outbox local transaccional implementada para pedidos, cobros, reservas y stock; sincronizador y servidor cloud pendientes |
| IA documental/Voicebot | Pendiente |
| Trazabilidad alimentaria | Pendiente |

## Orden recomendado de cierre de brechas

1. Completar el núcleo de venta: cuentas abiertas, división, descuentos, devoluciones, impresión y periféricos.
2. Completar la experiencia de camarero, cocina y QR, con estaciones y pagos integrados.
3. Cerrar ERP: formatos, lotes, traspasos, compras, escandallos y reposición.
4. Añadir reservas avanzadas, CRM, fidelización y campañas.
5. Implementar facturación fiscal con validación profesional.
6. Construir cloud SaaS, sincronización bidireccional y consola de cadena.
7. Incorporar B2B, web, kiosco e IA.

## Referencia de alcance

- HIOPOS — Restaurantes: https://www.hiopos.com/es/restaurantes
- HIOPOS — Bar/Cafetería: https://www.hiopos.com/es/bar-cafeteria
- HIOPOS — Innovaciones 2026: https://www.hiopos.com/es/noticias/la-innovacion-de-hiopos-en-hip-horeca-2026
