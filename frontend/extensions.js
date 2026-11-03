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
          prompt("Enlace privado de carta QR. Copia este enlace para compartirlo:", location.origin + result.menu_path);
        } catch (err) { alert(err.message); }
      };
    });
  };
})();
