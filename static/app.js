const state = {
  browsers: [],
  selectedBrowserId: null,
  currentBrowser: null,
  currentTabs: [],
  pendingArchiveAction: null,
  defaultSaveName: "",
};

const renderButton = document.getElementById("renderButton");
const archiveAllButton = document.getElementById("archiveAllButton");
const exportBackupButton = document.getElementById("exportBackupButton");
const heroStatus = document.getElementById("heroStatus");
const successBanner = document.getElementById("successBanner");
const successBannerTitle = document.getElementById("successBannerTitle");
const successBannerText = document.getElementById("successBannerText");
const downloadBackupButton = document.getElementById("downloadBackupButton");
const dismissSuccessButton = document.getElementById("dismissSuccessButton");
const browserModal = document.getElementById("browserModal");
const tabsModal = document.getElementById("tabsModal");
const saveAsModal = document.getElementById("saveAsModal");
const saveAsNameInput = document.getElementById("saveAsNameInput");
const saveAsStatus = document.getElementById("saveAsStatus");
const confirmSaveAsButton = document.getElementById("confirmSaveAsButton");
const cancelSaveAsButton = document.getElementById("cancelSaveAsButton");
const browserList = document.getElementById("browserList");
const browserStatus = document.getElementById("browserStatus");
const selectBrowserButton = document.getElementById("selectBrowserButton");
const closeBrowserModal = document.getElementById("closeBrowserModal");
const tabsList = document.getElementById("tabsList");
const tabsStatus = document.getElementById("tabsStatus");
const tabsModalTitle = document.getElementById("tabsModalTitle");
const selectAllButton = document.getElementById("selectAllButton");
const deselectAllButton = document.getElementById("deselectAllButton");
const archiveButton = document.getElementById("archiveButton");
const closeTabsModal = document.getElementById("closeTabsModal");
const historyContainer = document.getElementById("historyContainer");
const startAtLogin = document.getElementById("startAtLogin");
const appVersion = document.getElementById("appVersion");
const updateBanner = document.getElementById("updateBanner");
const updateBannerTitle = document.getElementById("updateBannerTitle");
const updateBannerText = document.getElementById("updateBannerText");
const updateBannerLink = document.getElementById("updateBannerLink");

function openModal(modal) {
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeModal(modal) {
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function formatApiError(detail, status) {
  const message = Array.isArray(detail)
    ? detail.map((item) => item.msg || item).join(", ")
    : detail || "Request failed";

  if (status === 404 && String(message).toLowerCase() === "not found") {
    return (
      "This feature requires Tab Archiver v1.1.0 or newer. " +
      "Close every Tab Archiver window, end any leftover Tab Archiver process, and launch the app again."
    );
  }

  return message;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(formatApiError(error.detail, response.status));
  }

  return response.json();
}

function versionAtLeast(version, minimum) {
  const parse = (value) =>
    String(value)
      .replace(/^v/, "")
      .split(".")
      .map((part) => parseInt(part, 10) || 0);

  const current = parse(version);
  const min = parse(minimum);
  const length = Math.max(current.length, min.length);

  for (let index = 0; index < length; index += 1) {
    const currentPart = current[index] || 0;
    const minPart = min[index] || 0;
    if (currentPart > minPart) {
      return true;
    }
    if (currentPart < minPart) {
      return false;
    }
  }

  return true;
}

function formatDate(dateString) {
  const date = new Date(`${dateString}T00:00:00`);
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function renderBrowserOptions() {
  browserList.innerHTML = "";

  if (!state.browsers.length) {
    browserList.innerHTML = "<p class='status-message'>No open browsers with detectable tabs were found.</p>";
    selectBrowserButton.disabled = true;
    return;
  }

  state.browsers.forEach((browser) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "browser-option";
    button.dataset.browserId = browser.id;
    button.innerHTML = `
      <strong>${browser.display_name}</strong>
      <div class="status-message">${browser.tab_count} open tab${browser.tab_count === 1 ? "" : "s"}</div>
    `;

    button.addEventListener("click", () => {
      state.selectedBrowserId = browser.id;
      document.querySelectorAll(".browser-option").forEach((node) => node.classList.remove("selected"));
      button.classList.add("selected");
      selectBrowserButton.disabled = false;
    });

    browserList.appendChild(button);
  });
}

function renderTabs() {
  tabsList.innerHTML = "";

  if (!state.currentTabs.length) {
    tabsList.innerHTML = "<p class='status-message'>No tabs found for this browser.</p>";
    return;
  }

  state.currentTabs.forEach((tab, index) => {
    const row = document.createElement("label");
    row.className = "checkbox-row";
    row.innerHTML = `
      <input type="checkbox" data-index="${index}" checked />
      <div class="checkbox-label">
        <div class="checkbox-title">${escapeHtml(tab.title || tab.url)}</div>
        <div class="checkbox-url">${escapeHtml(tab.url)}</div>
      </div>
    `;
    tabsList.appendChild(row);
  });
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setCheckboxState(checked) {
  tabsList.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = checked;
  });
}

function getSelectedTabs() {
  const selected = [];
  tabsList.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    if (checkbox.checked) {
      const index = Number(checkbox.dataset.index);
      selected.push(state.currentTabs[index]);
    }
  });
  return selected;
}

function createCollapsible(title, contentBuilder, extraClass = "", headerExtrasBuilder = null) {
  const wrapper = document.createElement("div");
  wrapper.className = `date-record ${extraClass}`.trim();

  const headerRow = document.createElement("div");
  headerRow.className = extraClass.includes("archive-record") ? "archive-header" : "";

  const header = document.createElement("button");
  header.type = "button";
  header.className = extraClass.includes("browser-record") ? "browser-header" : "date-header";
  header.innerHTML = `
    ${title}
    <span class="chevron">›</span>
  `;

  const content = document.createElement("div");
  content.className = extraClass.includes("browser-record") ? "tab-list" : "browser-list";
  contentBuilder(content);

  header.addEventListener("click", () => {
    wrapper.classList.toggle("expanded");
  });

  headerRow.appendChild(header);
  if (headerExtrasBuilder) {
    headerExtrasBuilder(headerRow);
  }

  wrapper.appendChild(headerRow);
  wrapper.appendChild(content);
  return wrapper;
}

function formatSavedAt(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

async function deleteArchive(saveName) {
  const confirmed = window.confirm(`Delete the saved archive "${saveName}"? This cannot be undone.`);
  if (!confirmed) {
    return;
  }

  await fetchJson(`/api/archives/${encodeURIComponent(saveName)}`, { method: "DELETE" });
  await loadHistory();
}

function renderHistory(history) {
  const archives = history.archives || {};
  const saveNames = Object.keys(archives).sort((a, b) => {
    const left = archives[a]?.updated_at || archives[a]?.created_at || "";
    const right = archives[b]?.updated_at || archives[b]?.created_at || "";
    return right.localeCompare(left) || b.localeCompare(a);
  });

  if (!saveNames.length) {
    historyContainer.innerHTML = "<p class='history-empty'>No archived tabs yet. Click Archive All Open Tabs to get started.</p>";
    return;
  }

  historyContainer.innerHTML = "";

  saveNames.forEach((saveName) => {
    const saveEntry = archives[saveName];
    const browsers = Object.values(saveEntry.browsers || {});
    const totalTabs = browsers.reduce((count, browser) => count + (browser.tabs || []).length, 0);
    const savedAt = formatSavedAt(saveEntry.updated_at || saveEntry.created_at);

    const archiveNode = createCollapsible(
      `<span>${escapeHtml(saveName)}</span><span class="archive-meta">${totalTabs} tab${totalTabs === 1 ? "" : "s"} · ${escapeHtml(savedAt)}</span>`,
      (browserContainer) => {
        browsers.forEach((browser) => {
          const tabs = browser.tabs || [];
          const browserNode = createCollapsible(
            `${escapeHtml(browser.browser_name)} (${tabs.length} site${tabs.length === 1 ? "" : "s"})`,
            (tabContainer) => {
              const actions = document.createElement("div");
              actions.className = "browser-actions";
              const openAllButton = document.createElement("button");
              openAllButton.type = "button";
              openAllButton.className = "secondary-button";
              openAllButton.textContent = "Open All";
              openAllButton.addEventListener("click", async (event) => {
                event.stopPropagation();
                try {
                  await fetchJson("/api/open-all", {
                    method: "POST",
                    body: JSON.stringify({
                      browser_key: browser.browser_key,
                      executable: browser.executable,
                      urls: tabs.map((tab) => tab.url),
                    }),
                  });
                } catch (error) {
                  alert(error.message);
                }
              });
              actions.appendChild(openAllButton);
              tabContainer.appendChild(actions);

              tabs.forEach((tab) => {
                const item = document.createElement("div");
                item.className = "tab-item";
                const link = document.createElement("a");
                link.className = "tab-link";
                link.href = tab.url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = tab.title || tab.url;
                item.appendChild(link);
                tabContainer.appendChild(item);
              });
            },
            "browser-record"
          );

          browserContainer.appendChild(browserNode);
        });
      },
      "archive-record",
      (headerRow) => {
        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "danger-button";
        deleteButton.textContent = "Delete";
        deleteButton.addEventListener("click", async (event) => {
          event.stopPropagation();
          try {
            await deleteArchive(saveName);
          } catch (error) {
            alert(error.message);
          }
        });
        headerRow.appendChild(deleteButton);
      }
    );

    historyContainer.appendChild(archiveNode);
  });
}

async function loadHistory() {
  const history = await fetchJson("/api/history");
  renderHistory(history);
}

async function openBrowserPicker() {
  browserStatus.textContent = "Scanning open browsers...";
  browserStatus.className = "status-message";
  state.selectedBrowserId = null;
  selectBrowserButton.disabled = true;

  try {
    const data = await fetchJson("/api/browsers");
    state.browsers = data.browsers || [];
    renderBrowserOptions();
    browserStatus.textContent = state.browsers.length
      ? "Select a browser to archive its open websites."
      : "";
    openModal(browserModal);
  } catch (error) {
    browserStatus.textContent = error.message;
    browserStatus.className = "status-message error";
    openModal(browserModal);
  }
}

async function openTabsPicker() {
  tabsStatus.textContent = "Loading open websites...";
  tabsStatus.className = "status-message";

  try {
    const data = await fetchJson(`/api/browsers/${state.selectedBrowserId}/tabs`);
    state.currentBrowser = data.browser;
    state.currentTabs = data.tabs || [];
    tabsModalTitle.textContent = `Open Websites - ${state.currentBrowser.display_name}`;
    renderTabs();
    tabsStatus.textContent = "";
    closeModal(browserModal);
    openModal(tabsModal);
  } catch (error) {
    tabsStatus.textContent = error.message;
    tabsStatus.className = "status-message error";
    openModal(tabsModal);
  }
}

async function loadDefaultSaveName() {
  const data = await fetchJson("/api/archive-name/default");
  state.defaultSaveName = data.save_name || "";
  return state.defaultSaveName;
}

function openSaveAsModal(action) {
  state.pendingArchiveAction = action;
  saveAsStatus.textContent = "";
  saveAsStatus.className = "status-message";
  saveAsNameInput.value = state.defaultSaveName;
  openModal(saveAsModal);
  saveAsNameInput.focus();
  saveAsNameInput.select();
}

async function performPendingArchive(saveName) {
  if (state.pendingArchiveAction === "all") {
    return fetchJson("/api/archive-all", {
      method: "POST",
      body: JSON.stringify({ save_name: saveName }),
    });
  }

  if (state.pendingArchiveAction === "single") {
    const selectedTabs = getSelectedTabs();
    return fetchJson("/api/archive", {
      method: "POST",
      body: JSON.stringify({
        browser_id: state.selectedBrowserId,
        save_name: saveName,
        tabs: selectedTabs,
      }),
    });
  }

  throw new Error("No archive action is pending.");
}

async function confirmSaveAs() {
  const saveName = saveAsNameInput.value.trim();
  if (!saveName) {
    saveAsStatus.textContent = "Enter a name for this archive.";
    saveAsStatus.className = "status-message error";
    return;
  }

  confirmSaveAsButton.disabled = true;
  saveAsStatus.textContent = "Saving archive...";
  saveAsStatus.className = "status-message";

  try {
    const result = await performPendingArchive(saveName);
    await loadHistory();
    closeModal(saveAsModal);

    if (state.pendingArchiveAction === "all") {
      showSuccessBanner(result);
      heroStatus.textContent = "";
    } else {
      closeModal(tabsModal);
      heroStatus.textContent = `Archive "${result.save_name}" saved to local history.`;
      heroStatus.className = "status-message success";
    }

    state.pendingArchiveAction = null;
  } catch (error) {
    saveAsStatus.textContent = error.message;
    saveAsStatus.className = "status-message error";
  } finally {
    confirmSaveAsButton.disabled = false;
  }
}

async function archiveSelectedTabs() {
  const selectedTabs = getSelectedTabs();
  if (!selectedTabs.length) {
    tabsStatus.textContent = "Select at least one website to archive.";
    tabsStatus.className = "status-message error";
    return;
  }

  tabsStatus.textContent = "";
  await loadDefaultSaveName();
  openSaveAsModal("single");
}

async function archiveAllOpenTabs() {
  archiveAllButton.disabled = true;
  heroStatus.textContent = "Scanning browsers...";
  heroStatus.className = "status-message";

  try {
    const data = await fetchJson("/api/browsers");
    if (!(data.browsers || []).length) {
      heroStatus.textContent = "No open browsers with detectable tabs were found.";
      heroStatus.className = "status-message error";
      return;
    }

    heroStatus.textContent = "";
    await loadDefaultSaveName();
    openSaveAsModal("all");
  } catch (error) {
    heroStatus.textContent = error.message;
    heroStatus.className = "status-message error";
  } finally {
    archiveAllButton.disabled = false;
  }
}

function showSuccessBanner(result) {
  if (!successBanner) {
    return;
  }
  successBanner.classList.remove("hidden");
  successBannerTitle.textContent = "Archive saved";
  successBannerText.textContent =
    `Saved "${result.save_name}" with ${result.total_tabs} tab${result.total_tabs === 1 ? "" : "s"} across ${result.browser_count} browser${result.browser_count === 1 ? "" : "s"}. ` +
    `A backup copy was saved to ${result.backup_path}. Copy this file to a USB drive or cloud folder before a full computer reset.`;
}

async function exportBackup() {
  exportBackupButton.disabled = true;
  heroStatus.textContent = "Creating backup copy...";
  heroStatus.className = "status-message";

  try {
    const result = await fetchJson("/api/export-backup", { method: "POST" });
    heroStatus.textContent = `Backup saved to ${result.backup_path}`;
    heroStatus.className = "status-message success";
  } catch (error) {
    heroStatus.textContent = error.message;
    heroStatus.className = "status-message error";
  } finally {
    exportBackupButton.disabled = false;
  }
}

function downloadBackupFile() {
  window.location.href = "/api/export-backup/download";
}

renderButton.addEventListener("click", openBrowserPicker);
archiveAllButton.addEventListener("click", archiveAllOpenTabs);
exportBackupButton.addEventListener("click", exportBackup);
downloadBackupButton.addEventListener("click", downloadBackupFile);
dismissSuccessButton.addEventListener("click", () => successBanner.classList.add("hidden"));
closeBrowserModal.addEventListener("click", () => closeModal(browserModal));
closeTabsModal.addEventListener("click", () => closeModal(tabsModal));
selectBrowserButton.addEventListener("click", openTabsPicker);
selectAllButton.addEventListener("click", () => setCheckboxState(true));
deselectAllButton.addEventListener("click", () => setCheckboxState(false));
archiveButton.addEventListener("click", archiveSelectedTabs);
confirmSaveAsButton.addEventListener("click", confirmSaveAs);
cancelSaveAsButton.addEventListener("click", () => {
  state.pendingArchiveAction = null;
  closeModal(saveAsModal);
});
saveAsModal.addEventListener("click", (event) => {
  if (event.target === saveAsModal) {
    state.pendingArchiveAction = null;
    closeModal(saveAsModal);
  }
});
saveAsNameInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    confirmSaveAs();
  }
});

browserModal.addEventListener("click", (event) => {
  if (event.target === browserModal) closeModal(browserModal);
});

tabsModal.addEventListener("click", (event) => {
  if (event.target === tabsModal) closeModal(tabsModal);
});

loadHistory().catch((error) => {
  historyContainer.innerHTML = `<p class="status-message error">${escapeHtml(error.message)}</p>`;
});

async function loadSettings() {
  const settings = await fetchJson("/api/settings");
  if (appVersion) {
    appVersion.textContent = `v${settings.version || ""}`;
  }
  if (startAtLogin) {
    startAtLogin.checked = Boolean(settings.start_at_login);
  }

  if (!versionAtLeast(settings.version, "1.1.0")) {
    heroStatus.textContent =
      "You are connected to an older Tab Archiver server. Close all Tab Archiver windows and restart the app to use Archive All and Export Backup.";
    heroStatus.className = "status-message error";
  }
}

async function saveSettings() {
  if (!startAtLogin) {
    return;
  }
  await fetchJson("/api/settings", {
    method: "POST",
    body: JSON.stringify({
      start_at_login: startAtLogin.checked,
    }),
  });
}

async function loadUpdateStatus() {
  const update = await fetchJson("/api/update");
  if (!update.update_available || !updateBanner) {
    return;
  }

  updateBanner.classList.remove("hidden");
  updateBannerTitle.textContent = `Update available: v${update.latest_version}`;
  updateBannerText.textContent = `You are running v${update.current_version}. Download the latest release to get the newest fixes and improvements.`;
  updateBannerLink.href = update.download_url || update.release_page_url;
}

if (startAtLogin) {
  startAtLogin.addEventListener("change", () => {
    saveSettings().catch((error) => {
      alert(error.message);
    });
  });
}

loadSettings().catch(() => {});
loadUpdateStatus().catch(() => {});
loadDefaultSaveName().catch(() => {});
