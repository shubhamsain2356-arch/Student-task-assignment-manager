/* ============================================================
   TaskBoard — front-end JavaScript
   Handles: loading tasks from the API, search/filter/sort,
   marking complete, deleting (with confirmation), and the
   add/edit task forms.
   ============================================================ */

// Keep the full list of tasks in memory so we can filter client-side
// without re-fetching from the server on every keystroke.
let allTasks = [];
let taskPendingDelete = null;

/* ---------------- Shared helper: talk to the API ---------------- */
async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }
  return data;
}

/* ============================================================
   TASKS LIST PAGE (/tasks)
   ============================================================ */
function initTasksPage() {
  loadTasks();

  document.getElementById("search-input").addEventListener("input", renderTasks);
  document.getElementById("filter-subject").addEventListener("change", renderTasks);
  document.getElementById("filter-status").addEventListener("change", renderTasks);
  document.getElementById("filter-priority").addEventListener("change", renderTasks);
  document.getElementById("sort-due").addEventListener("change", renderTasks);

  document.getElementById("confirm-cancel").addEventListener("click", closeConfirmDialog);
  document.getElementById("confirm-delete").addEventListener("click", confirmDeleteTask);
}

async function loadTasks() {
  try {
    allTasks = await apiRequest("/api/tasks");
    populateSubjectFilter();
    renderTasks();
  } catch (err) {
    document.getElementById("task-list").innerHTML =
      `<p class="loading-msg">Could not load tasks: ${err.message}</p>`;
  }
}

function populateSubjectFilter() {
  const select = document.getElementById("filter-subject");
  const subjects = [...new Set(allTasks.map((t) => t.subject).filter(Boolean))].sort();
  select.innerHTML = '<option value="">All subjects</option>';
  subjects.forEach((subject) => {
    const option = document.createElement("option");
    option.value = subject;
    option.textContent = subject;
    select.appendChild(option);
  });
}

function renderTasks() {
  const search = document.getElementById("search-input").value.trim().toLowerCase();
  const subject = document.getElementById("filter-subject").value;
  const status = document.getElementById("filter-status").value;
  const priority = document.getElementById("filter-priority").value;
  const sortDue = document.getElementById("sort-due").value;

  let filtered = allTasks.filter((task) => {
    if (search && !task.title.toLowerCase().includes(search)) return false;
    if (subject && task.subject !== subject) return false;
    if (status && task.status !== status) return false;
    if (priority && task.priority !== priority) return false;
    return true;
  });

  if (sortDue === "asc" || sortDue === "desc") {
    filtered = filtered.slice().sort((a, b) => {
      const dateA = a.due_date || "9999-99-99";
      const dateB = b.due_date || "9999-99-99";
      return sortDue === "asc" ? dateA.localeCompare(dateB) : dateB.localeCompare(dateA);
    });
  }

  const listEl = document.getElementById("task-list");
  const emptyEl = document.getElementById("empty-state");

  if (filtered.length === 0) {
    listEl.innerHTML = "";
    emptyEl.style.display = "block";
    return;
  }
  emptyEl.style.display = "none";
  listEl.innerHTML = filtered.map(renderTaskCard).join("");

  // Wire up buttons on the freshly-rendered cards
  filtered.forEach((task) => {
    const card = document.getElementById(`task-${task.id}`);
    card.querySelector(".btn-toggle").addEventListener("click", () => toggleComplete(task));
    card.querySelector(".btn-delete").addEventListener("click", () => openConfirmDialog(task.id));
  });
}

function renderTaskCard(task) {
  const overdueText = task.is_overdue ? " (overdue)" : "";
  const dueLabel = task.due_date ? `Due ${task.due_date}${overdueText}` : "No due date";
  const isDone = task.status === "Completed";

  return `
    <div class="task-card ${isDone ? "is-completed" : ""}" id="task-${task.id}">
      <div class="task-card-main">
        <div class="task-card-title-row">
          <span class="task-card-title">${escapeHtml(task.title)}</span>
          <span class="pill pill-${task.priority.toLowerCase()}">${task.priority}</span>
          <span class="pill pill-status-${task.status.toLowerCase()}">${task.status}</span>
        </div>
        ${task.description ? `<p class="task-card-desc">${escapeHtml(task.description)}</p>` : ""}
        <div class="task-card-meta">
          <span>${escapeHtml(task.subject || "General")}</span>
          <span class="${task.is_overdue ? "text-overdue" : ""}">${dueLabel}</span>
        </div>
      </div>
      <div class="task-card-actions">
        <button class="icon-btn done btn-toggle" title="${isDone ? "Mark as pending" : "Mark as completed"}">✓</button>
        <a class="icon-btn" href="/tasks/edit/${task.id}" title="Edit">✎</a>
        <button class="icon-btn danger btn-delete" title="Delete">🗑</button>
      </div>
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function toggleComplete(task) {
  const newStatus = task.status === "Completed" ? "Pending" : "Completed";
  try {
    await apiRequest(`/api/tasks/${task.id}`, {
      method: "PUT",
      body: JSON.stringify({ status: newStatus }),
    });
    task.status = newStatus;
    renderTasks();
  } catch (err) {
    alert("Could not update task: " + err.message);
  }
}

function openConfirmDialog(taskId) {
  taskPendingDelete = taskId;
  document.getElementById("confirm-overlay").style.display = "flex";
}

function closeConfirmDialog() {
  taskPendingDelete = null;
  document.getElementById("confirm-overlay").style.display = "none";
}

async function confirmDeleteTask() {
  if (!taskPendingDelete) return;
  try {
    await apiRequest(`/api/tasks/${taskPendingDelete}`, { method: "DELETE" });
    allTasks = allTasks.filter((t) => t.id !== taskPendingDelete);
    closeConfirmDialog();
    populateSubjectFilter();
    renderTasks();
  } catch (err) {
    alert("Could not delete task: " + err.message);
    closeConfirmDialog();
  }
}

/* ============================================================
   ADD TASK PAGE (/tasks/add)
   ============================================================ */
function initAddTaskForm() {
  const form = document.getElementById("add-task-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.getElementById("form-error");
    errorBox.style.display = "none";

    const payload = {
      title: document.getElementById("title").value,
      description: document.getElementById("description").value,
      subject: document.getElementById("subject").value,
      due_date: document.getElementById("due_date").value,
      priority: document.getElementById("priority").value,
    };

    try {
      await apiRequest("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
      window.location.href = "/tasks";
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.style.display = "block";
    }
  });
}

/* ============================================================
   EDIT TASK PAGE (/tasks/edit/<id>)
   ============================================================ */
function initEditTaskForm() {
  const form = document.getElementById("edit-task-form");
  const taskId = form.dataset.taskId;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.getElementById("form-error");
    errorBox.style.display = "none";

    const payload = {
      title: document.getElementById("title").value,
      description: document.getElementById("description").value,
      subject: document.getElementById("subject").value,
      due_date: document.getElementById("due_date").value,
      priority: document.getElementById("priority").value,
      status: document.getElementById("status").value,
    };

    try {
      await apiRequest(`/api/tasks/${taskId}`, { method: "PUT", body: JSON.stringify(payload) });
      window.location.href = "/tasks";
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.style.display = "block";
    }
  });
}

/* ---------------- Auto-dismiss flash messages ---------------- */
document.addEventListener("DOMContentLoaded", () => {
  const flashWrap = document.querySelector(".flash-wrap");
  if (flashWrap) {
    setTimeout(() => { flashWrap.style.display = "none"; }, 4000);
  }
});