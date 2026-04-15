let currentMode = 'nlp';
let radarChartInstance = null;
let currentRecommendations = [];
const API_BASE_URL = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) ? window.APP_CONFIG.API_BASE_URL : '';

function apiUrl(path) {
    return `${API_BASE_URL}${path}`;
}

// Lógica Visual de las Pestañas
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', (e) => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        currentMode = e.target.dataset.mode;
        
        const input = document.getElementById('searchInput');
        if(currentMode === 'nlp') {
            input.placeholder = "Ej: quiero música alegre para entrenar...";
        } else if(currentMode === 'contenido') {
            input.placeholder = "Escribe un artista exacto (ej: Queen o Coldplay)...";
        } else if(currentMode === 'spotify_import') {
            input.placeholder = "Pega el link de una playlist de Spotify pública...";
        }
    });
});

document.getElementById('searchBtn').addEventListener('click', () => performSearch());
document.getElementById('searchInput').addEventListener('keypress', (e) => {
    if(e.key === 'Enter') performSearch();
});

document.getElementById('exportBtn').addEventListener('click', () => exportToSpotify());
document.getElementById('spotifyConnectBtn').addEventListener('click', () => connectSpotify());
document.getElementById('spotifyDisconnectBtn').addEventListener('click', () => disconnectSpotify());
refreshSpotifyStatus();

// Lógica Funcional Async a Backend Python
async function performSearch(overrideType = null, overrideIndex = null) {
    console.log("🚀 performSearch iniciada");
    const query = document.getElementById('searchInput').value.trim();
    if(!query) {
        console.warn("⚠️ Query vacía");
        return;
    }

    const loader = document.getElementById('loader');
    const wrapper = document.getElementById('resultsWrapper');
    const errorMsg = document.getElementById('errorMsg');
    const exportBtn = document.getElementById('exportBtn');
    
    // Ocultar modal si existe
    closeModal();

    wrapper.classList.add('hidden');
    exportBtn.classList.add('hidden');
    errorMsg.classList.add('hidden');
    loader.classList.remove('hidden');

    try {
        const payload = {
            query: query,
            mode: currentMode
        };
        if(overrideType) payload.override_type = overrideType;
        if(overrideIndex !== null) payload.override_index = overrideIndex;

        console.log("📡 Enviando fetch a /api/recommend", payload);
        const response = await fetch(apiUrl('/api/recommend'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify(payload)
        });

        console.log("📥 Respuesta recibida de fetch", response);
        if (!response.ok) {
            const errorText = await response.text();
            console.error("❌ HTTP Error:", response.status, errorText);
            throw new Error(`Servidor respondió con error ${response.status}: ${errorText || "Error interno"}`);
        }

        const data = await response.json();
        console.log("📦 Data parseada:", data);

        if(data.status === 'success') {
            currentRecommendations = data.data;
            console.log("✅ Recomendaciones recibidas:", currentRecommendations.length);
            
            // Mostrar el contenedor de resultados
            wrapper.classList.remove('hidden');
            wrapper.style.setProperty('display', 'flex', 'important'); 

            // Forzar render del grid y chart si wrapper estaba oculto
            console.log("🎨 Forzando render de grid y chart");
            renderCards(data.data);
            if(data.chart_data && Object.keys(data.chart_data).length > 0) {
                if (typeof Chart === 'undefined') {
                    console.error("❌ Chart.js no cargado. Revisa conexión a internet.");
                    errorMsg.textContent = "❌ Error: Librería de gráficos no cargada (Chart.js).";
                    errorMsg.classList.remove('hidden');
                } else {
                    renderChart(data.chart_data);
                }
            }

            // Mostrar el botón de exportar si hay resultados
            if(currentRecommendations.length > 0) {
                console.log("🚀 Mostrando botón de exportar");
                exportBtn.classList.remove('hidden');
                exportBtn.style.setProperty('display', 'flex', 'important'); 
            } else {
                console.warn("⚠️ No hay recomendaciones para exportar.");
            }
        } else if (data.status === 'conflict') {
            showConflictModal(data);
        } else {
            console.error("❌ Backend error:", data.message);
            errorMsg.textContent = data.message;
            errorMsg.classList.remove('hidden');
        }
    } catch (err) {
        console.error("💥 Critical JS/Network error:", err);
        errorMsg.textContent = `❌ Error: ${err.message || "Error desconocido"}`;
        errorMsg.classList.remove('hidden');
    } finally {
        loader.classList.add('hidden');
    }
}

async function exportToSpotify() {
    if(currentRecommendations.length === 0) return;
    
    const exportBtn = document.getElementById('exportBtn');
    const originalText = exportBtn.innerText;
    exportBtn.disabled = true;
    exportBtn.innerText = "⏳ Exportando...";

    try {
        const payload = {
            playlist_name: `AI Recs: ${document.getElementById('searchInput').value.substring(0, 20)}`,
            tracks: currentRecommendations.map(t => ({ track_name: t.track_name, artist: t.artist }))
        };

        const response = await fetch(apiUrl('/api/export'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if(data.status === 'success') {
            const urlMsg = data.playlist_url ? `\n${data.playlist_url}` : "";
            alert(`✅ ${data.message || "Playlist creada con éxito."}${urlMsg}`);
        } else {
            alert("❌ Error: " + data.message);
        }
    } catch (err) {
        alert("❌ Error de conexión al exportar.");
    } finally {
        exportBtn.disabled = false;
        exportBtn.innerText = originalText;
    }
}

async function connectSpotify() {
    try {
        const response = await fetch(apiUrl('/api/spotify/login'), { credentials: 'include' });
        const data = await response.json();
        if (data.status !== 'success' || !data.auth_url) {
            throw new Error(data.message || 'No se pudo iniciar Spotify OAuth.');
        }
        window.location.href = data.auth_url;
    } catch (err) {
        alert(`❌ Error conectando Spotify: ${err.message}`);
    }
}

async function disconnectSpotify() {
    try {
        await fetch(apiUrl('/api/spotify/logout'), {
            method: 'POST',
            credentials: 'include'
        });
        await refreshSpotifyStatus();
    } catch (err) {
        alert("❌ No se pudo desconectar Spotify.");
    }
}

async function refreshSpotifyStatus() {
    const statusText = document.getElementById('spotifyStatusText');
    const connectBtn = document.getElementById('spotifyConnectBtn');
    const disconnectBtn = document.getElementById('spotifyDisconnectBtn');
    try {
        const response = await fetch(apiUrl('/api/spotify/status'), { credentials: 'include' });
        const data = await response.json();
        if (data.connected) {
            statusText.textContent = `Conectado: ${data.user.display_name}`;
            connectBtn.classList.add('hidden');
            disconnectBtn.classList.remove('hidden');
        } else {
            statusText.textContent = 'Spotify no conectado';
            connectBtn.classList.remove('hidden');
            disconnectBtn.classList.add('hidden');
        }
    } catch (err) {
        statusText.textContent = 'No se pudo validar Spotify';
        connectBtn.classList.remove('hidden');
        disconnectBtn.classList.add('hidden');
    }
}

// Renderización de Spider Chart Geométrico
function renderChart(chartData) {
    const ctx = document.getElementById('dnaChart').getContext('2d');
    
    if (radarChartInstance) {
        radarChartInstance.destroy();
    }

    const labels = Object.keys(chartData.target).map(lbl => lbl.toUpperCase());
    const dataTarget = Object.values(chartData.target);
    const dataRecs = Object.values(chartData.recommendations);

    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '🔍 Búsqueda Original',
                    data: dataTarget,
                    backgroundColor: 'rgba(56, 189, 248, 0.3)',
                    borderColor: '#38bdf8',
                    borderWidth: 2,
                    pointBackgroundColor: '#38bdf8'
                },
                {
                    label: '🤖 Match Generado',
                    data: dataRecs,
                    backgroundColor: 'rgba(167, 139, 250, 0.4)',
                    borderColor: '#a78bfa',
                    borderWidth: 2,
                    pointBackgroundColor: '#a78bfa'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#f8fafc', font: { family: 'Outfit', size: 13 } } }
            },
            scales: {
                r: {
                    angleLines: { color: 'rgba(255,255,255,0.1)' },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    pointLabels: { color: '#cbd5e1', font: { family: 'Outfit', size: 10 } },
                    ticks: { display: false, min: 0 }
                }
            }
        }
    });
}

// Modales Interactivas
function showConflictModal(data) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'activeModal';
    
    const box = document.createElement('div');
    box.className = 'modal-box';
    
    const title = document.createElement('h2');
    title.innerText = "¡Alerta de Coincidencia Múltiple!";
    
    const desc = document.createElement('p');
    desc.innerText = data.message;
    
    const btnContainer = document.createElement('div');
    btnContainer.className = 'modal-buttons';
    
    if(data.type === 'artist_vs_track') {
        const btnArtist = document.createElement('button');
        btnArtist.className = 'btn-modal purple';
        btnArtist.innerHTML = "👨‍🎤 Buscar el Autor";
        btnArtist.onclick = () => performSearch('artista', null);
        
        const btnTrack = document.createElement('button');
        btnTrack.className = 'btn-modal pink';
        btnTrack.innerHTML = "🎧 Buscar la Canción";
        btnTrack.onclick = () => performSearch('cancion', null);
        
        btnContainer.appendChild(btnArtist);
        btnContainer.appendChild(btnTrack);
        
    } else if (data.type === 'multiple_tracks') {
        const list = document.createElement('div');
        list.className = 'track-list';
        
        data.options.forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.className = 'btn-modal-list';
            btn.innerHTML = `<strong>${opt.track_name}</strong> por ${opt.artist} <em>(${Math.round(opt.popularity)}⭐)</em>`;
            btn.onclick = () => performSearch(null, idx);
            list.appendChild(btn);
        });
        btnContainer.appendChild(list);
    }
    
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-cancel';
    cancelBtn.innerText = "Cancelar Búsqueda";
    cancelBtn.onclick = closeModal;
    
    box.appendChild(title);
    box.appendChild(desc);
    box.appendChild(btnContainer);
    box.appendChild(cancelBtn);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
}

function closeModal() {
    const modal = document.getElementById('activeModal');
    if(modal) modal.remove();
}

function renderCards(tracks) {
    const grid = document.getElementById('resultsGrid');
    grid.innerHTML = '';

    tracks.forEach(track => {
        const div = document.createElement('div');
        div.className = 'card';
        // Inyectando Match %
        let matchPercent = track.match_percent > 0 ? track.match_percent : 0;
        div.innerHTML = `
            <div class="match-badge">${Math.round(matchPercent)}% Match</div>
            <h3 style="margin-top: 15px;">${track.track_name}</h3>
            <p class="artist">${track.artist}</p>
            <div class="meta">
                <span>⭐ Pop: ${Math.round(track.popularity)}</span>
                <span>🎵 ${track.track_genre.toUpperCase().substring(0, 15)}</span>
            </div>
        `;
        grid.appendChild(div);
    });
}
