let appConfig = {};
let categories = {};
let selectedCategory = "";
let selectedKeyword = "";
let latestRows = [];

const qs = (selector) => document.querySelector(selector);

function formatPrice(value) {
    const num = Number(value || 0);
    if (!num) return "-";
    return new Intl.NumberFormat("ko-KR").format(num) + "원";
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
    if (!payload.ok) {
        throw new Error(payload.error || "요청 실패");
    }
    return payload;
}

async function init() {
    await loadConfig();
    await loadCategories();
    await loadLatest();
    bindEvents();
}

function bindEvents() {
    qs("#openConfigBtn").addEventListener("click", () => qs("#configDialog").showModal());
    qs("#saveConfigBtn").addEventListener("click", saveConfig);
    qs("#addKeywordBtn").addEventListener("click", addKeyword);
    qs("#collectBtn").addEventListener("click", collectSelected);
}

async function loadConfig() {
    const payload = await api("/api/config");
    appConfig = payload.config;
    qs("#apiStatus").textContent = appConfig.has_api_key ? "API Key 저장됨" : "API Key 미설정";
    qs("#apiStatus").className = appConfig.has_api_key ? "status ok" : "status muted";
    qs("#topNSelect").value = String(appConfig.top_n || 100);
    qs("#configTopN").value = String(appConfig.top_n || 100);
    qs("#cooldownInput").value = String(appConfig.cooldown_minutes || 30);
    qs("#metricCooldown").textContent = `${appConfig.cooldown_minutes || 30}분`;
}

async function saveConfig(event) {
    event.preventDefault();
    const clientId = qs("#clientIdInput").value.trim();
    const clientSecret = qs("#clientSecretInput").value.trim();
    if (!clientId || !clientSecret) {
        setMessage("Client ID와 Client Secret을 입력해주세요.", "error");
        return;
    }

    await api("/api/config", {
        method: "POST",
        body: JSON.stringify({
            client_id: clientId,
            client_secret: clientSecret,
            top_n: Number(qs("#configTopN").value),
            cooldown_minutes: Number(qs("#cooldownInput").value || 30),
        }),
    });
    qs("#configDialog").close();
    qs("#clientSecretInput").value = "";
    setMessage("API Key가 저장되었습니다.", "ok");
    await loadConfig();
}

async function loadCategories() {
    const payload = await api("/api/categories");
    categories = payload.categories;
    const first = Object.keys(categories)[0] || "";
    if (!selectedCategory) selectedCategory = first;
    renderCategories();
    renderKeywords();
}

function renderCategories() {
    const container = qs("#categoryList");
    container.innerHTML = Object.keys(categories)
        .map((category) => `
            <button class="category-btn ${category === selectedCategory ? "active" : ""}" data-category="${category}">
                <span>${category}</span>
                <span class="tag">${categories[category].length}</span>
            </button>
        `)
        .join("");

    container.querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", async () => {
            selectedCategory = button.dataset.category;
            selectedKeyword = "";
            renderCategories();
            renderKeywords();
            await loadLatest();
        });
    });
}

function renderKeywords() {
    const rows = categories[selectedCategory] || [];
    const container = qs("#keywordList");
    container.innerHTML = rows
        .map((row, index) => `
            <div class="keyword-row">
                <label>
                    <input type="checkbox" class="keyword-check" value="${row.keyword}" ${index < 10 ? "checked" : ""}>
                    <span>${row.keyword}</span>
                </label>
                <span class="tag">${row.is_default === "Y" ? "기본" : "추가"}</span>
            </div>
        `)
        .join("");

    qs("#pageTitle").textContent = selectedCategory ? `${selectedCategory} 가격 비교` : "가격 비교";
    qs("#pageSubtitle").textContent = "동일 키워드는 30분 쿨타임 안에서 기존 .t1 파일을 사용합니다.";
}

async function addKeyword() {
    const keyword = qs("#newKeywordInput").value.trim();
    if (!selectedCategory || !keyword) {
        setMessage("카테고리와 추가 키워드를 확인해주세요.", "error");
        return;
    }
    await api("/api/keyword", {
        method: "POST",
        body: JSON.stringify({ category: selectedCategory, keyword }),
    });
    qs("#newKeywordInput").value = "";
    setMessage(`추가 키워드 저장: ${keyword}`, "ok");
    await loadCategories();
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
        setMessage("조회할 키워드를 선택해주세요.", "error");
        return;
    }
    if (keywords.length > 10) {
        setMessage("한 번에 최대 10개 키워드까지만 조회할 수 있습니다.", "error");
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
            }),
        });
        latestRows = payload.rows;
        qs("#lastRun").textContent = `마지막 조회: ${new Date().toLocaleString("ko-KR")}`;
        setMessage("대시보드를 갱신했습니다.", "ok");
        renderLatest();
    } catch (error) {
        setMessage(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "선택 키워드 조회";
    }
}

async function loadLatest() {
    if (!selectedCategory) return;
    const payload = await api(`/api/latest?category=${encodeURIComponent(selectedCategory)}`);
    latestRows = payload.rows;
    renderLatest();
}

function renderLatest() {
    const tbody = qs("#latestTableBody");
    if (!latestRows.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty">표시할 데이터가 없습니다.</td></tr>`;
        updateMetrics();
        return;
    }

    tbody.innerHTML = latestRows
        .map((row) => {
            const change = row.avg_change;
            const changeClass = change > 0 ? "up" : change < 0 ? "down" : "flat";
            const changeText = change === null || change === undefined ? "-" : formatPrice(Math.abs(change));
            return `
                <tr data-keyword="${row.keyword}" class="${row.keyword === selectedKeyword ? "active" : ""}">
                    <td><strong>${row.keyword}</strong> <span class="tag">${row.is_default === "Y" ? "기본" : "추가"}</span></td>
                    <td>${row.snapshot_time || "-"}</td>
                    <td class="price">${formatPrice(row.avg_price)}</td>
                    <td class="price">${formatPrice(row.min_price)}</td>
                    <td class="price">${formatPrice(row.max_price)}</td>
                    <td>${row.count || 0} / ${row.search_total || 0}</td>
                    <td class="${changeClass}">${changeText}</td>
                </tr>
            `;
        })
        .join("");

    tbody.querySelectorAll("tr").forEach((tr) => {
        tr.addEventListener("click", () => selectKeyword(tr.dataset.keyword));
    });

    updateMetrics();
    const firstWithData = latestRows.find((row) => row.count > 0);
    if (!selectedKeyword && firstWithData) selectKeyword(firstWithData.keyword);
    renderTopItems(latestRows.find((row) => row.keyword === selectedKeyword));
}

function updateMetrics() {
    const activeRows = latestRows.filter((row) => row.count > 0);
    qs("#metricKeywords").textContent = String(latestRows.length);
    if (!activeRows.length) {
        qs("#metricMinAvg").textContent = "-";
        qs("#metricAvg").textContent = "-";
        return;
    }

    const minAvg = activeRows.reduce((sum, row) => sum + Number(row.min_price || 0), 0) / activeRows.length;
    const avg = activeRows.reduce((sum, row) => sum + Number(row.avg_price || 0), 0) / activeRows.length;
    qs("#metricMinAvg").textContent = formatPrice(minAvg);
    qs("#metricAvg").textContent = formatPrice(avg);
}

async function selectKeyword(keyword) {
    selectedKeyword = keyword;
    document.querySelectorAll("#latestTableBody tr").forEach((tr) => {
        tr.classList.toggle("active", tr.dataset.keyword === keyword);
    });
    qs("#selectedKeywordLabel").textContent = keyword;
    renderTopItems(latestRows.find((row) => row.keyword === keyword));

    const payload = await api(`/api/trend?category=${encodeURIComponent(selectedCategory)}&keyword=${encodeURIComponent(keyword)}`);
    renderTrend(payload.trend);
}

function renderTrend(rows) {
    const ctx = qs("#trendChart");
    const rect = ctx.parentElement.getBoundingClientRect();
    const scale = window.devicePixelRatio || 1;
    ctx.width = rect.width * scale;
    ctx.height = rect.height * scale;
    const canvas = ctx.getContext("2d");
    canvas.scale(scale, scale);
    canvas.clearRect(0, 0, rect.width, rect.height);

    if (!rows.length) {
        canvas.fillStyle = "#6b7785";
        canvas.font = "14px Arial";
        canvas.fillText("추이 데이터가 없습니다.", 20, 30);
        return;
    }

    const series = [
        { key: "avg_price", label: "평균가", color: "#2563eb" },
        { key: "min_price", label: "최저가", color: "#16a34a" },
        { key: "max_price", label: "최고가", color: "#dc2626" },
    ];
    const values = rows.flatMap((row) => series.map((item) => Number(row[item.key] || 0))).filter(Boolean);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = { left: 64, right: 20, top: 20, bottom: 50 };
    const width = rect.width - pad.left - pad.right;
    const height = rect.height - pad.top - pad.bottom;
    const range = Math.max(1, max - min);
    const x = (index) => pad.left + (rows.length === 1 ? width / 2 : (width * index) / (rows.length - 1));
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
    canvas.fillText(formatPrice(max), 4, pad.top + 4);
    canvas.fillText(formatPrice(min), 4, pad.top + height);

    series.forEach((item) => {
        canvas.strokeStyle = item.color;
        canvas.lineWidth = 2;
        canvas.beginPath();
        rows.forEach((row, index) => {
            const px = x(index);
            const py = y(row[item.key]);
            if (index === 0) canvas.moveTo(px, py);
            else canvas.lineTo(px, py);
        });
        canvas.stroke();
    });

    const lastDate = rows[rows.length - 1]?.snapshot_time || "";
    canvas.fillStyle = "#6b7785";
    canvas.font = "12px Arial";
    canvas.fillText(rows[0]?.snapshot_time || "", pad.left, rect.height - 18);
    canvas.textAlign = "right";
    canvas.fillText(lastDate, pad.left + width, rect.height - 18);
    canvas.textAlign = "left";

    let legendX = pad.left;
    series.forEach((item) => {
        canvas.fillStyle = item.color;
        canvas.fillRect(legendX, rect.height - 12, 10, 3);
        canvas.fillStyle = "#1f2933";
        canvas.fillText(item.label, legendX + 14, rect.height - 8);
        legendX += 72;
    });
}

function renderTopItems(row) {
    const container = qs("#topItems");
    if (!row || !row.items || !row.items.length) {
        container.innerHTML = `<div class="empty">최신 스냅샷이 없습니다.</div>`;
        return;
    }

    container.innerHTML = row.items
        .map((item) => `
            <div class="item">
                <a class="item-title" href="${item.link}" target="_blank" rel="noreferrer">${item.rank}. ${item.title}</a>
                <div class="item-meta">${item.mall_name || "-"} · ${formatPrice(item.price)} · ID ${item.item_id}</div>
            </div>
        `)
        .join("");
}

document.addEventListener("DOMContentLoaded", () => {
    init().catch((error) => setMessage(error.message, "error"));
});
