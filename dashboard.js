let appConfig = {};
let categories = {};
let selectedCategory = "";
let selectedKeyword = "";
let latestRows = [];
let currentTrend = null;
let hiddenPairKeys = new Set();

const qs = (selector) => document.querySelector(selector);
const colors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#0891b2", "#be123c", "#4d7c0f"];

function formatPrice(value) {
    const num = Number(value || 0);
    if (!num) return "-";
    return new Intl.NumberFormat("ko-KR").format(num) + "원";
}

function formatRate(value) {
    if (value === null || value === undefined || value === "") return "-";
    return `${Number(value).toFixed(1)}%`;
}

function setMessage(text, type = "") {
    const el = qs("#message");
    el.textContent = text || "";
    el.className = `message ${type}`.trim();
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "요청 실패");
    return payload;
}

async function init() {
    bindEvents();
    await loadConfig();
    await loadCategories();
    await loadLatest();
    await loadLatestReport();
}

function bindEvents() {
    qs("#openConfigBtn").addEventListener("click", () => qs("#configDialog").showModal());
    qs("#testDataBtn").addEventListener("click", loadTestData);
    qs("#saveConfigBtn").addEventListener("click", saveConfig);
    qs("#addKeywordBtn").addEventListener("click", openSkuDialog);
    qs("#saveSkuBtn").addEventListener("click", saveSkuMapping);
    qs("#collectBtn").addEventListener("click", collectSelected);
    qs("#categorySelect").addEventListener("change", onCategoryChange);
    qs("#productTypeSelect").addEventListener("change", loadLatest);
    qs("#saveCategoryCooldownBtn").addEventListener("click", saveCategoryCooldown);
    window.addEventListener("resize", drawTrend);
}

function currentProductType() {
    return qs("#productTypeSelect").value || "all";
}

function cooldownForCategory(category) {
    return Number(appConfig.category_cooldowns?.[category] || appConfig.cooldown_minutes || 30);
}

async function loadConfig() {
    const payload = await api("/api/config");
    appConfig = payload.config;
    qs("#apiStatus").textContent = appConfig.has_api_key ? "API Key 저장됨" : "API Key 미설정";
    qs("#apiStatus").className = appConfig.has_api_key ? "status ok" : "status muted";
    qs("#topNSelect").value = String(appConfig.top_n || 100);
    qs("#configTopN").value = String(appConfig.top_n || 100);
    qs("#cooldownInput").value = String(appConfig.cooldown_minutes || 30);
    updateCooldownDisplay();
}

async function loadTestData() {
    const button = qs("#testDataBtn");
    button.disabled = true;
    setMessage("TV test 데이터를 생성 중입니다.");
    try {
        const payload = await api("/api/test_data", {
            method: "POST",
            body: JSON.stringify({ product_type: currentProductType() }),
        });
        categories = payload.categories;
        selectedCategory = payload.result.category;
        selectedKeyword = "";
        latestRows = payload.rows || [];
        updateReportLink(payload.report);
        renderSummary(payload.summary);
        renderCategorySelect();
        renderKeywords();
        renderLatest();
        setMessage("TV test 데이터를 불러왔습니다.", "ok");
    } catch (error) {
        setMessage(error.message, "error");
    } finally {
        button.disabled = false;
    }
}

async function saveConfig(event) {
    event.preventDefault();
    await api("/api/config", {
        method: "POST",
        body: JSON.stringify({
            client_id: qs("#clientIdInput").value.trim(),
            client_secret: qs("#clientSecretInput").value.trim(),
            top_n: Number(qs("#configTopN").value),
            cooldown_minutes: Number(qs("#cooldownInput").value || 30),
            category_cooldowns: appConfig.category_cooldowns || {},
        }),
    });
    qs("#configDialog").close();
    qs("#clientIdInput").value = "";
    qs("#clientSecretInput").value = "";
    setMessage("조회 설정을 저장했습니다.", "ok");
    await loadConfig();
}

async function saveCategoryCooldown() {
    if (!selectedCategory) return;
    await api("/api/category_cooldown", {
        method: "POST",
        body: JSON.stringify({ category: selectedCategory, minutes: Number(qs("#categoryCooldownInput").value || 30) }),
    });
    setMessage(`${selectedCategory} 쿨다운을 저장했습니다.`, "ok");
    await loadConfig();
}

async function loadCategories() {
    const payload = await api("/api/categories");
    categories = payload.categories;
    const first = Object.keys(categories)[0] || "";
    if (!selectedCategory || !categories[selectedCategory]) selectedCategory = first;
    renderCategorySelect();
    renderKeywords();
}

function renderCategorySelect() {
    const select = qs("#categorySelect");
    select.innerHTML = Object.keys(categories)
        .map((category) => `<option value="${escapeAttr(category)}">${escapeHtml(category)} (${categories[category].length})</option>`)
        .join("");
    select.value = selectedCategory;
    updateCooldownDisplay();
}

async function onCategoryChange() {
    selectedCategory = qs("#categorySelect").value;
    selectedKeyword = "";
    hiddenPairKeys = new Set();
    renderKeywords();
    updateCooldownDisplay();
    await loadLatest();
}

function updateCooldownDisplay() {
    const minutes = cooldownForCategory(selectedCategory);
    qs("#metricCooldown").textContent = `${minutes}분`;
    qs("#categoryCooldownInput").value = String(minutes);
}

function renderKeywords() {
    const rows = categories[selectedCategory] || [];
    const container = qs("#keywordList");
    container.innerHTML = rows
        .map((row, index) => `
            <div class="keyword-row">
                <label>
                    <input type="checkbox" class="keyword-check" value="${escapeAttr(row.keyword)}" ${index < 10 ? "checked" : ""}>
                    <span class="keyword-text">
                        <strong>${escapeHtml(row.own_sku || row.keyword)}</strong>
                        <small>${escapeHtml(row.competitor_sku || "-")} · 기준가 ${formatPrice(row.base_price)}</small>
                    </span>
                </label>
                <span class="tag">${row.is_default === "Y" ? "기본" : "추가"}</span>
                <button class="delete-keyword" data-keyword="${escapeAttr(row.keyword)}" title="삭제">x</button>
            </div>
        `)
        .join("");

    container.querySelectorAll(".delete-keyword").forEach((button) => {
        button.addEventListener("click", () => deleteKeyword(button.dataset.keyword));
    });
}

function openSkuDialog() {
    qs("#ownSkuInput").value = "";
    qs("#competitorSkuInput").value = "";
    qs("#basePriceInput").value = "";
    qs("#skuDialog").showModal();
}

async function saveSkuMapping(event) {
    event.preventDefault();
    const ownSku = qs("#ownSkuInput").value.trim().toUpperCase();
    const competitorSku = qs("#competitorSkuInput").value.trim().toUpperCase();
    const basePrice = Number(qs("#basePriceInput").value || 0);
    if (!selectedCategory || !ownSku || !competitorSku || !basePrice) {
        setMessage("당사 모델코드, 경쟁사 모델코드, 기준가를 모두 입력해주세요.", "error");
        return;
    }
    await api("/api/keyword", {
        method: "POST",
        body: JSON.stringify({ category: selectedCategory, own_sku: ownSku, competitor_sku: competitorSku, base_price: basePrice }),
    });
    qs("#skuDialog").close();
    setMessage(`모델코드를 등록했습니다: ${ownSku} / ${competitorSku}`, "ok");
    await loadCategories();
    await loadLatest();
}

async function deleteKeyword(keyword) {
    await api("/api/delete_keyword", {
        method: "POST",
        body: JSON.stringify({ category: selectedCategory, keyword }),
    });
    if (selectedKeyword === keyword) selectedKeyword = "";
    setMessage("모델코드를 삭제했습니다.", "ok");
    await loadCategories();
    await loadLatest();
}

function selectedKeywords() {
    return Array.from(document.querySelectorAll(".keyword-check:checked")).map((el) => el.value);
}

async function collectSelected() {
    if (!appConfig.has_api_key) {
        setMessage("먼저 API Key를 설정해주세요.", "error");
        qs("#configDialog").showModal();
        return;
    }

    const keywords = selectedKeywords();
    if (!selectedCategory || keywords.length === 0) {
        setMessage("조회할 모델코드를 선택해주세요.", "error");
        return;
    }
    if (keywords.length > 10) {
        setMessage("한 번에 최대 10개 모델까지만 조회할 수 있습니다.", "error");
        return;
    }

    const button = qs("#collectBtn");
    button.disabled = true;
    button.textContent = "조회 중";
    setMessage("네이버 API 조회 또는 캐시 파일 로드 중입니다.");

    try {
        const payload = await api("/api/collect", {
            method: "POST",
            body: JSON.stringify({
                category: selectedCategory,
                keywords,
                top_n: Number(qs("#topNSelect").value),
                product_type: currentProductType(),
            }),
        });
        latestRows = payload.rows || [];
        updateReportLink(payload.report);
        renderSummary(payload.summary);
        qs("#lastRun").textContent = `마지막 조회: ${new Date().toLocaleString("ko-KR")}`;
        setMessage("대시보드를 갱신했습니다.", "ok");
        renderLatest();
    } catch (error) {
        setMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "선택 모델 조회";
    }
}

async function loadLatest() {
    if (!selectedCategory) return;
    const payload = await api(`/api/latest?category=${encodeURIComponent(selectedCategory)}&product_type=${encodeURIComponent(currentProductType())}`);
    latestRows = payload.rows || [];
    renderSummary(payload.summary);
    renderLatest();
}

async function loadLatestReport() {
    try {
        const payload = await api("/api/report/latest");
        updateReportLink(payload.report);
    } catch (error) {
        updateReportLink(null);
    }
}

function updateReportLink(report) {
    const link = qs("#latestReportLink");
    if (!link) return;
    const path = report?.path || "";
    if (!path) {
        link.textContent = "생성 전";
        link.href = "#";
        link.setAttribute("aria-disabled", "true");
        return;
    }
    const webPath = "/" + path.replace(/\\/g, "/").replace(/^\/+/, "");
    link.textContent = path;
    link.href = webPath;
    link.removeAttribute("aria-disabled");
}

function renderSummary(lines) {
    const defaults = [
        "기준가 대비 10% 이상 낮은 게시물만 표시합니다.",
        "기준가 또는 경쟁사 가격이 없는 모델은 제외합니다.",
        "상세 게시물은 URL 클릭 시 확인 가능합니다.",
    ];
    qs("#aiSummaryList").innerHTML = (lines && lines.length ? lines : defaults)
        .slice(0, 3)
        .map((line) => `<li>${escapeHtml(line)}</li>`)
        .join("");
}

function renderLatest() {
    const tbody = qs("#latestTableBody");
    if (!latestRows.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty">기준가 대비 10% 이상 낮은 게시물이 없습니다.</td></tr>`;
        updateLatestDate();
        updateMetrics();
        renderTopItems(null);
        return;
    }

    tbody.innerHTML = latestRows.map((row) => {
        const maxDiscount = maxDiscountRate(row.low_items || []);
        return `
            <tr data-keyword="${escapeAttr(row.keyword)}" class="${row.keyword === selectedKeyword ? "active" : ""}">
                <td>
                    <div class="model-cell">
                        <div>
                            <strong>당사 ${escapeHtml(row.own_sku || "-")}</strong>
                            <small>경쟁사 ${escapeHtml(row.competitor_sku || "-")}</small>
                        </div>
                    </div>
                </td>
                <td class="price base-price">${formatPrice(row.base_price)}</td>
                <td class="price low-price-cell">
                    ${lowestBlock("당사 최저가", row.own_lowest)}
                    ${lowestBlock("경쟁사 최저가", row.competitor_lowest)}
                </td>
                <td><strong>${Number(row.low_count || 0).toLocaleString("ko-KR")}건</strong></td>
                <td class="down">${formatRate(maxDiscount)}</td>
                <td>${topItemLink(row.low_items?.[0])}</td>
                <td><button class="table-action download-data" data-keyword="${escapeAttr(row.keyword)}">CSV</button></td>
            </tr>
        `;
    }).join("");

    tbody.querySelectorAll("tr").forEach((tr) => {
        tr.addEventListener("click", () => selectKeyword(tr.dataset.keyword));
    });
    tbody.querySelectorAll(".download-data").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            downloadLatestCsv(button.dataset.keyword);
        });
    });

    updateLatestDate();
    updateMetrics();
    const firstWithData = latestRows.find((row) => Number(row.low_count || 0) > 0);
    if (!selectedKeyword && firstWithData) selectKeyword(firstWithData.keyword);
    renderTopItems(latestRows.find((row) => row.keyword === selectedKeyword) || firstWithData);
}

function lowestBlock(label, item) {
    if (!item) {
        return `<div class="lowest-block"><span>${label}: -</span></div>`;
    }
    const price = formatPrice(item.lprice || item.price);
    const rate = item.discount_rate !== null && item.discount_rate !== undefined ? ` (${formatRate(item.discount_rate)})` : "";
    const url = item.link || "";
    const link = url
        ? `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer" onclick="event.stopPropagation()">${escapeHtml(url)}</a>`
        : `<span class="muted-inline">URL 없음</span>`;
    return `<div class="lowest-block"><strong>${label}: ${price}${rate}</strong>${link}</div>`;
}

function topItemLink(item) {
    if (!item) return "-";
    if (!item.link) return formatPrice(item.lprice || item.price);
    return `<a class="table-action" href="${escapeAttr(item.link)}" target="_blank" rel="noreferrer" onclick="event.stopPropagation()">상세 URL</a>`;
}

function maxDiscountRate(items) {
    const values = (items || []).map((item) => Number(item.discount_rate)).filter((value) => !Number.isNaN(value));
    if (!values.length) return null;
    return Math.min(...values);
}

function updateLatestDate() {
    const times = latestRows
        .map((row) => row.snapshot_time)
        .filter(Boolean)
        .map((value) => new Date(String(value).replace(" ", "T")))
        .filter((value) => !Number.isNaN(value.getTime()));
    if (!times.length) {
        qs("#latestUpdatedAt").textContent = "기준가 대비 10% 이상 낮은 게시물 기준 · 최신 업데이트: -";
        return;
    }
    const latest = new Date(Math.max(...times.map((value) => value.getTime())));
    qs("#latestUpdatedAt").textContent = `기준가 대비 10% 이상 낮은 게시물 기준 · 최신 업데이트: ${latest.toLocaleString("ko-KR")}`;
}

function updateMetrics() {
    qs("#metricKeywords").textContent = String(latestRows.length);
    qs("#metricLowCount").textContent = `${latestRows.reduce((sum, row) => sum + Number(row.low_count || 0), 0).toLocaleString("ko-KR")}건`;
    const maxRate = maxDiscountRate(latestRows.flatMap((row) => row.low_items || []));
    qs("#metricMaxDiscount").textContent = formatRate(maxRate);
    updateCooldownDisplay();
}

async function selectKeyword(keyword) {
    const changed = selectedKeyword !== keyword;
    selectedKeyword = keyword;
    if (changed) hiddenPairKeys = new Set();
    document.querySelectorAll("#latestTableBody tr").forEach((tr) => {
        tr.classList.toggle("active", tr.dataset.keyword === keyword);
    });
    const row = latestRows.find((item) => item.keyword === keyword);
    qs("#selectedKeywordLabel").textContent = row ? `${row.own_sku} / ${row.competitor_sku}` : keyword;
    qs("#ownChartTitle").textContent = row ? `삼성 ${row.own_sku} 가격 추이` : "당사 모델코드 가격 추이";
    qs("#competitorChartTitle").textContent = row ? `경쟁사 ${row.competitor_sku} 가격 추이` : "경쟁사 모델코드 가격 추이";
    renderTopItems(row);

    const payload = await api(`/api/trend?category=${encodeURIComponent(selectedCategory)}&keyword=${encodeURIComponent(keyword)}&product_type=${encodeURIComponent(currentProductType())}`);
    renderTrend(payload.trend);
}

function renderTrend(trend) {
    currentTrend = trend;
    drawTrend();
}

function drawTrend() {
    if (!currentTrend) return;
    drawTrendCanvas("#ownTrendChart", currentTrend.own?.series || [], currentTrend.snapshots || [], "당사 모델코드 가격 추이 데이터가 없습니다.");
    drawTrendCanvas("#competitorTrendChart", currentTrend.competitor?.series || [], currentTrend.snapshots || [], "경쟁사 모델코드 가격 추이 데이터가 없습니다.");
    renderLegend();
}

function drawTrendCanvas(selector, allSeries, snapshots, emptyText) {
    const canvasEl = qs(selector);
    const rect = canvasEl.parentElement.getBoundingClientRect();
    const scale = window.devicePixelRatio || 1;
    canvasEl.width = Math.max(300, rect.width) * scale;
    canvasEl.height = Math.max(220, rect.height) * scale;
    canvasEl.style.width = `${rect.width}px`;
    canvasEl.style.height = `${rect.height}px`;

    const canvas = canvasEl.getContext("2d");
    canvas.setTransform(scale, 0, 0, scale, 0, 0);
    canvas.clearRect(0, 0, rect.width, rect.height);

    const series = allSeries
        .map((line, index) => ({ ...line, pair_index: index }))
        .filter((line) => !hiddenPairKeys.has(String(line.pair_index)));
    if (!snapshots.length || !series.length) {
        canvas.fillStyle = "#6b7785";
        canvas.font = "14px Arial";
        canvas.fillText(emptyText, 20, 30);
        return;
    }

    const values = series.flatMap((line) => snapshots.map((time) => Number(line.points[time] || 0))).filter(Boolean);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = { left: 72, right: 24, top: 18, bottom: 42 };
    const width = rect.width - pad.left - pad.right;
    const height = rect.height - pad.top - pad.bottom;
    const range = Math.max(1, max - min);
    const x = (index) => pad.left + (snapshots.length === 1 ? width / 2 : (width * index) / (snapshots.length - 1));
    const y = (value) => pad.top + height - ((Number(value || 0) - min) / range) * height;

    canvas.strokeStyle = "#dfe5eb";
    canvas.lineWidth = 1;
    canvas.beginPath();
    canvas.moveTo(pad.left, pad.top);
    canvas.lineTo(pad.left, pad.top + height);
    canvas.lineTo(pad.left + width, pad.top + height);
    canvas.stroke();

    canvas.fillStyle = "#6b7785";
    canvas.font = "12px Arial";
    canvas.fillText(formatPrice(max), 6, pad.top + 4);
    canvas.fillText(formatPrice(min), 6, pad.top + height);

    series.forEach((line, index) => {
        const color = colors[index % colors.length];
        canvas.strokeStyle = color;
        canvas.lineWidth = 1.8;
        canvas.beginPath();
        let started = false;
        snapshots.forEach((time, snapIndex) => {
            const value = line.points[time];
            if (!value) {
                started = false;
                return;
            }
            const px = x(snapIndex);
            const py = y(value);
            if (!started) {
                canvas.moveTo(px, py);
                started = true;
            } else {
                canvas.lineTo(px, py);
            }
        });
        canvas.stroke();
    });

    canvas.fillStyle = "#6b7785";
    canvas.font = "12px Arial";
    canvas.fillText(shortTime(snapshots[0]), pad.left, rect.height - 16);
    canvas.textAlign = "right";
    canvas.fillText(shortTime(snapshots[snapshots.length - 1]), pad.left + width, rect.height - 16);
    canvas.textAlign = "left";
}

function renderLegend() {
    const legend = qs("#trendLegend");
    const own = (currentTrend?.own?.series || []).map((line, index) => ({ ...line, pair_index: index, side_label: "삼성" }));
    const competitor = (currentTrend?.competitor?.series || []).map((line, index) => ({ ...line, pair_index: index, side_label: "경쟁사" }));
    const series = [...own, ...competitor].filter((line) => !hiddenPairKeys.has(String(line.pair_index)));
    legend.innerHTML = series.slice(0, 12).map((line, index) => `
        <div class="legend-item">
            <span class="legend-color" style="background:${colors[index % colors.length]}"></span>
            <span class="legend-text">${line.side_label} ${line.pair_index + 1}. ${escapeHtml(line.mall_name || "-")} · ${escapeHtml(line.title)}</span>
            <button class="legend-remove" data-pair="${escapeAttr(line.pair_index)}" title="당사/경쟁사 같은 순번 함께 숨기기">x</button>
        </div>
    `).join("");
    legend.querySelectorAll(".legend-remove").forEach((button) => {
        button.addEventListener("click", () => {
            hiddenPairKeys.add(String(button.dataset.pair));
            drawTrend();
        });
    });
}

function renderTopItems(row) {
    const container = qs("#topItems");
    const items = row?.low_items || [];
    if (!items.length) {
        container.innerHTML = `<div class="empty">기준가 대비 10% 이상 낮은 게시물이 없습니다.</div>`;
        return;
    }

    container.innerHTML = items.slice(0, 20).map((item, index) => `
        <div class="item">
            ${item.link ? `<a class="item-title" href="${escapeAttr(item.link)}" target="_blank" rel="noreferrer">${index + 1}. ${escapeHtml(item.title)}</a>` : `<div class="item-title">${index + 1}. ${escapeHtml(item.title)}</div>`}
            <div class="item-meta">${item.side === "competitor" ? "경쟁사" : "당사"} · ${escapeHtml(item.mall_name || "-")} · ${formatPrice(item.lprice || item.price)} · ${formatRate(item.discount_rate)} · 모델코드 ${escapeHtml(item.sku || "-")}</div>
        </div>
    `).join("");
}

function downloadLatestCsv(keyword) {
    const row = latestRows.find((item) => item.keyword === keyword);
    const items = row?.low_items || [];
    if (!items.length) {
        setMessage("다운로드할 저가 게시물 데이터가 없습니다.", "error");
        return;
    }

    const columns = [
        "snapshot_time", "category", "keyword", "side", "sku", "rank", "item_id", "product_id", "product_type",
        "title", "mall_name", "lprice", "discount_rate", "link", "brand", "maker", "search_total", "raw_json",
    ];
    const rows = [columns.join(",")];
    items.forEach((item) => {
        rows.push(columns.map((column) => csvCell(item[column])).join(","));
    });

    const csv = "\ufeff" + rows.join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8-sig" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${safeFileName(row.category)}_${safeFileName(row.own_sku)}_${safeFileName(row.competitor_sku)}_low_top20.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    setMessage("저가 게시물 TOP20 데이터를 CSV로 저장했습니다.", "ok");
}

function csvCell(value) {
    const text = String(value ?? "");
    return `"${text.replace(/"/g, '""')}"`;
}

function safeFileName(value) {
    return String(value ?? "").replace(/[<>:"/\\|?*\s]+/g, "_").replace(/^_+|_+$/g, "") || "data";
}

function shortTime(value) {
    if (!value) return "";
    return String(value).replace(/^\d{4}-/, "").replace(":00", "");
}

function escapeAttr(value) {
    return String(value ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeHtml(value) {
    return escapeAttr(value);
}

document.addEventListener("DOMContentLoaded", () => {
    init().catch((error) => setMessage(error.message, "error"));
});
