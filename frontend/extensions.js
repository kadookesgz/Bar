// TPV V2 UI extensions: reservations, stock, QR and kitchen workflows.
(function () {
  const nav = document.querySelector(".nav");
  const cashNav = nav.querySelector('[data-view="cash"]');
  function addNav(id, label) {
    if (nav.querySelector('[data-view="' + id + '"]')) return;
    const b = document.createElement("button");
    b.dataset.view = id;
    b.textContent = label;
    b.onclick = function () { switchView(id); };
    nav.insertBefore(b, cashNav);
  }
  addNav("reservations", "▣ Reservas");
  addNav("inventory", "▤ Almacén");

  const cashSection = document.getElementById("cash");
  ["reservations", "inventory"].forEach(function (id) {
    const section = document.createElement("section");
    section.id = id;
    section.className = "view";
    if (id === "reservations") {
      section.innerHTML = '<div class="heading"><div><h1>Reservas</h1><div class="sub">Agenda de clientes y asignación de mesas</div></div><button id="newReservationBtn">＋ Nueva reserva</button></div><div id="reservationList" class="list"></div>';
    } else {
      section.innerHTML = '<div class="heading"><div><h1>Almacén</h1><div class="sub">Existencias, costes y movimientos de inventario</div></div><button id="newStockItemBtn">＋ Artículo</button></div><div id="inventoryList" class="list"></div>';
    }
    cashSection.parentNode.insertBefore(section, cashSection);
  });
  document.getElementById("newReservationBtn").onclick = newReservation;
  document.getElementById("newStockItemBtn").onclick = newStockItem;

  const originalSwitchView = switchView;
  window.switchView = function (id) {
    if (id !== "reservations" && id !== "inventory") return originalSwitchView(id);
    document.querySelectorAll(".view").forEach(function (v) { v.classList.toggle("active", v.id === id); });
    document.querySelectorAll(".nav button").forEach(function (b) { b.classList.toggle("active", b.dataset.view === id); });
    document.getElementById("pageTitle").textContent = id === "reservations" ? "Reservas" : "Almacén";
    if (id === "reservations") renderReservations();
    if (id === "inventory") renderInventory();
  };

  let reservations = [];
  let stockItems = [];
  const originalLoadAll = loadAll;
  window.loadAll = async function () {
    await originalLoadAll();
    try {
      const data = await Promise.all([api("/api/v1/reservations"), api("/api/v1/inventory/items")]);
      reservations = data[0];
      stockItems = data[1];
      renderReservations();
      renderInventory();
      await loadKitchen();
    } catch (err) { console.error(err); }
  };

  window.renderReservations = function () {
    const root = document.getElementById("reservationList");
    if (!root) return;
    root.innerHTML = reservations.map(function (r) {
      return '<div class="listrow"><div><strong>' + esc(r.customer_name) + ' · ' + r.party_size + ' personas</strong><small>' +
        new Date(r.starts_at).toLocaleString("es-ES") + ' · ' + esc(r.phone || "Sin teléfono") +
        '</small></div><span class="pill ' + (r.status === "confirmed" ? "green" : "amber") + '">' + esc(r.status) + '</span></div>';
    }).join("") || '<div class="empty">No hay reservas registradas</div>';
  };

  window.newReservation = function () {
    const d = new Date(Date.now() + 86400000);
    d.setMinutes(0, 0, 0);
    const date = d.getFullYear() + "-" + String(d.getMonth()+1).padStart(2,"0") + "-" + String(d.getDate()).padStart(2,"0") + "T" + String(d.getHours()).padStart(2,"0") + ":00";
    modal("Nueva reserva",
      '<label>Nombre<input name="customer_name" required></label>' +
      '<div class="formgrid"><label>Teléfono<input name="phone"></label><label>Personas<input name="party_size" type="number" min="1" value="2"></label></div>' +
      '<label>Fecha y hora<input name="starts_at" type="datetime-local" required value="' + date + '"></label>' +
      '<label>Duración (minutos)<input name="duration_minutes" type="number" value="120"></label>' +
      '<label>Notas<textarea name="notes"></textarea></label>',
      function (data) {
        return api("/api/v1/reservations", {method:"POST", body:JSON.stringify({
          customer_name:data.customer_name, phone:data.phone || null, party_size:Number(data.party_size),
          starts_at:new Date(data.starts_at).toISOString(), duration_minutes:Number(data.duration_minutes), notes:data.notes || null
        })});
      }
    );
  };

  window.renderInventory = function () {
    const root = document.getElementById("inventoryList");
    if (!root) return;
    root.innerHTML = stockItems.map(function (item) {
      return '<div class="listrow"><div><strong>' + esc(item.name) + ' ' +
        (item.low_stock ? '<span class="pill red">Stock bajo</span>' : '') +
        '</strong><small>' + esc(item.unit) + ' · Coste ' + money(item.cost_per_unit) + ' / unidad</small></div>' +
        '<div style="text-align:right"><b>' + esc(item.current_stock) + ' ' + esc(item.unit) + '</b><br>' +
        '<button class="secondary stock-movement" data-item-id="' + item.id + '" style="padding:6px 9px;margin-top:5px">Movimiento</button></div></div>';
    }).join("") || '<div class="empty">No hay artículos de almacén</div>';
    root.querySelectorAll(".stock-movement").forEach(function (button) {
      button.onclick = function () { adjustStock(button.dataset.itemId); };
    });
  };

  window.newStockItem = function () {
    modal("Nuevo artículo de almacén",
      '<label>Nombre<input name="name" required></label>' +
      '<div class="formgrid"><label>Unidad<input name="unit" value="ud"></label>' +
      '<label>Stock mínimo<input name="minimum_stock" type="number" min="0" step=".001" value="0"></label>' +
      '<label>Coste por unidad (€)<input name="cost_per_unit" type="number" min="0" step=".0001" value="0"></label></div>',
      function (data) {
        return api("/api/v1/inventory/items", {method:"POST", body:JSON.stringify({
          name:data.name, unit:data.unit, minimum_stock:Number(data.minimum_stock), cost_per_unit:Number(data.cost_per_unit)
        })});
      }
    );
  };

  window.adjustStock = async function (id) {
    const quantity = prompt("Cantidad del movimiento. Positivo para entrada y negativo para salida.");
    if (quantity === null || !Number(quantity)) return;
    try {
      await api("/api/v1/inventory/items/" + id + "/movements", {method:"POST", body:JSON.stringify({
        quantity:Math.abs(Number(quantity)), movement_type:Number(quantity) < 0 ? "sale" : "purchase",
        note:"Movimiento manual desde TPV"
      })});
      await loadAll();
    } catch (err) { alert(err.message); }
  };

  window.loadKitchen = async function () {
    try {
      kitchen = await api("/api/v1/orders/kitchen/queue");
      const root = document.getElementById("kitchenQueue");
      root.innerHTML = kitchen.map(function (k) {
        return '<div class="card"><div class="toolbar" style="justify-content:space-between"><b>Comanda #' + k.order_number +
          '</b><span class="pill amber">' + esc(k.order_status) + '</span></div><h3>' + esc(k.product_name) + ' × ' +
          esc(k.quantity) + '</h3><div class="sub">' + (k.table_id ? "Mesa" : "Barra") + ' · ' +
          new Date(k.opened_at).toLocaleTimeString("es-ES",{hour:"2-digit",minute:"2-digit"}) + '</div><div class="muted" style="margin:10px 0">' +
          esc(k.notes || "Sin observaciones") + '</div><button class="secondary kitchen-ready" data-line-id="' + k.line_id + '">Marcar preparado</button></div>';
      }).join("") || '<div class="empty">No hay comandas pendientes de cocina</div>';
      root.querySelectorAll(".kitchen-ready").forEach(function (button) {
        button.onclick = function () { setKitchenStatus(button.dataset.lineId, "ready"); };
      });
    } catch (err) { document.getElementById("kitchenQueue").innerHTML = '<div class="empty">' + esc(err.message) + '</div>'; }
  };

  window.setKitchenStatus = async function (lineId, status) {
    try {
      await api("/api/v1/kitchen/lines/" + lineId + "/status", {method:"PATCH", body:JSON.stringify({status:status})});
      await loadAll();
    } catch (err) { alert(err.message); }
  };

  window.renderTables = function () {
    const root = document.getElementById("tableGrid");
    if (!root) return;
    const occupied = new Set((orders || []).filter(function (o) { return o.table_id; }).map(function (o) { return o.table_id; }));
    root.innerHTML = tables.map(function (table) {
      return '<div class="tablecard ' + (occupied.has(table.id) ? "occupied" : "") + '">' +
        '<div class="tname">' + esc(table.label) + '</div><div class="tstate">' +
        (occupied.has(table.id) ? "● Ocupada" : "○ Libre") + ' · ' + table.capacity + ' plazas</div>' +
        '<div class="toolbar" style="margin-top:10px"><button class="secondary open-table" data-table-id="' + table.id + '" style="padding:6px 9px">Abrir</button>' +
        '<button class="make-qr" data-table-id="' + table.id + '" style="padding:6px 9px">QR</button></div></div>';
    }).join("") || '<div class="empty">Todavía no hay mesas configuradas. Pulsa Nueva mesa.</div>';
    root.querySelectorAll(".open-table").forEach(function (button) {
      button.onclick = function () { selectTable(button.dataset.tableId); };
    });
    root.querySelectorAll(".make-qr").forEach(function (button) {
      button.onclick = async function () {
        try {
          const result = await api("/api/v1/floor/tables/" + button.dataset.tableId + "/qr-token", {method:"POST"});
          const popup = window.open("", "_blank");
          if (!popup) { prompt("Enlace privado de carta QR:", location.origin + result.menu_path); return; }
          popup.document.write('<html><head><title>QR de mesa</title><style>body{font:16px system-ui;text-align:center;padding:30px}img{width:280px;height:280px}p{word-break:break-all}</style></head><body><h2>Escanea para ver la carta</h2><img src="data:image/png;base64,' + result.qr_png_base64 + '"><p>' + location.origin + result.menu_path + '</p><button onclick="window.print()">Imprimir QR</button></body></html>');
          popup.document.close();
        } catch (err) { alert(err.message); }
      };
    });
  };

  ["employees", "customers", "reports"].forEach(function (id) {
    const button = document.createElement("button");
    button.dataset.view = id;
    button.textContent = id === "employees" ? "♙ Equipo" : id === "customers" ? "♡ Clientes" : "▥ Informes";
    button.onclick = function () { switchView(id); };
    nav.insertBefore(button, cashNav);
    const section = document.createElement("section");
    section.id = id;
    section.className = "view";
    if (id === "employees") section.innerHTML = '<div class="heading"><div><h1>Equipo</h1><div class="sub">Usuarios, perfiles y permisos del establecimiento</div></div><button id="newEmployeeBtn">＋ Empleado</button></div><div id="employeeList" class="list"></div>';
    if (id === "customers") section.innerHTML = '<div class="heading"><div><h1>Clientes y fidelización</h1><div class="sub">Ficha de cliente e historial de puntos</div></div><button id="newCustomerBtn">＋ Cliente</button></div><div id="customerList" class="list"></div>';
    if (id === "reports") section.innerHTML = '<div class="heading"><div><h1>Informes</h1><div class="sub">Ventas, ticket medio y productos más vendidos</div></div><button id="refreshReportBtn" class="secondary">↻ Actualizar</button></div><div id="reportContent"></div>';
    cashSection.parentNode.insertBefore(section, cashSection);
  });
  document.getElementById("newEmployeeBtn").onclick = newEmployee;
  document.getElementById("newCustomerBtn").onclick = newCustomer;
  document.getElementById("refreshReportBtn").onclick = loadReport;

  const oldExtendedLoadAll = loadAll;
  window.loadAll = async function () {
    await oldExtendedLoadAll();
    try {
      const data = await Promise.all([api("/api/v1/employees"), api("/api/v1/customers")]);
      employees = data[0]; customers = data[1];
      renderEmployees(); renderCustomers();
    } catch (err) { console.error(err); }
  };
  let employees = [], customers = [];

  const oldSwitchWithTwo = switchView;
  window.switchView = function (id) {
    if (["employees", "customers", "reports"].indexOf(id) < 0) return oldSwitchWithTwo(id);
    document.querySelectorAll(".view").forEach(function (v) { v.classList.toggle("active", v.id === id); });
    document.querySelectorAll(".nav button").forEach(function (b) { b.classList.toggle("active", b.dataset.view === id); });
    document.getElementById("pageTitle").textContent = id === "employees" ? "Equipo" : id === "customers" ? "Clientes" : "Informes";
    if (id === "employees") renderEmployees();
    if (id === "customers") renderCustomers();
    if (id === "reports") loadReport();
  };

  window.renderEmployees = function () {
    const root = document.getElementById("employeeList");
    if (!root) return;
    root.innerHTML = employees.map(function (e) {
      return '<div class="listrow"><div><strong>' + esc(e.display_name) + '</strong><small>' + esc(e.email) + '</small></div><span class="pill">' + esc(e.role) + '</span></div>';
    }).join("") || '<div class="empty">No hay empleados registrados</div>';
  };
  window.newEmployee = function () {
    modal("Añadir empleado",
      '<label>Nombre<input name="display_name" required></label><label>Correo<input name="email" type="email" required></label>' +
      '<label>Contraseña inicial (mínimo 12 caracteres)<input name="password" type="password" minlength="12" required></label>' +
      '<label>Perfil<select name="role"><option value="waiter">Camarero</option><option value="kitchen">Cocina</option><option value="cashier">Caja</option><option value="manager">Encargado</option></select></label>',
      function (d) { return api("/api/v1/employees", {method:"POST",body:JSON.stringify(d)}); }
    );
  };
  window.renderCustomers = function () {
    const root = document.getElementById("customerList");
    if (!root) return;
    root.innerHTML = customers.map(function (c) {
      return '<div class="listrow"><div><strong>' + esc(c.name) + '</strong><small>' + esc(c.email || c.phone || "Sin contacto") + '</small></div><span class="pill green">' + c.loyalty_points + ' puntos</span></div>';
    }).join("") || '<div class="empty">No hay clientes registrados</div>';
  };
  window.newCustomer = function () {
    modal("Nuevo cliente",
      '<label>Nombre<input name="name" required></label><label>Correo<input name="email" type="email"></label><label>Teléfono<input name="phone"></label><label>Notas<textarea name="notes"></textarea></label>',
      function (d) { return api("/api/v1/customers", {method:"POST",body:JSON.stringify({name:d.name,email:d.email||null,phone:d.phone||null,notes:d.notes||null})}); }
    );
  };
  window.loadReport = async function () {
    const root = document.getElementById("reportContent");
    root.innerHTML = '<div class="empty">Cargando informe…</div>';
    try {
      const r = await api("/api/v1/reports/daily");
      root.innerHTML = '<div class="grid stats"><div class="card"><div class="statlabel">Ventas cobradas hoy</div><div class="statvalue">' + money(r.sales_total) + '</div></div>' +
        '<div class="card"><div class="statlabel">Tickets cobrados</div><div class="statvalue">' + r.paid_orders + '</div></div>' +
        '<div class="card"><div class="statlabel">Ticket medio</div><div class="statvalue">' + money(r.average_ticket) + '</div></div></div>' +
        '<div class="grid twocol"><div class="card"><h3>Productos más vendidos</h3>' +
        (r.top_products.map(function (p) { return '<div class="listrow"><b>' + esc(p.name) + '</b><span>' + esc(p.quantity) + ' uds · ' + money(p.sales) + '</span></div>'; }).join("") || '<p class="muted">Sin ventas cerradas hoy.</p>') +
        '</div><div class="card"><h3>Formas de pago</h3>' +
        (r.payments_by_method.map(function (p) { return '<div class="listrow"><b>' + esc(p.method) + '</b><span>' + money(p.amount) + '</span></div>'; }).join("") || '<p class="muted">Sin cobros hoy.</p>') + '</div></div>';
    } catch (err) { root.innerHTML = '<div class="notice">' + esc(err.message) + '</div>'; }
  };

})();
