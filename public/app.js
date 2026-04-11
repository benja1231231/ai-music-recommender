let currentMode = 'nlp';
let radarChartInstance = null;

// Lógica Visual de las Pestañas
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', (e) => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        currentMode = e.target.dataset.mode;
        
        const input = document.getElementById('searchInput');
        if(currentMode === 'nlp') {
            input.placeholder = "Ej: quiero música alegre para entrenar...";
        } else {
            input.placeholder = "Escribe un artista exacto (ej: Queen o Coldplay)...";
        }
    });
});

document.getElementById('searchBtn').addEventListener('click', () => performSearch());
document.getElementById('searchInput').addEventListener('keypress', (e) => {
    if(e.key === 'Enter') performSearch();
});

// Lógica Funcional Async a Backend Python
async function performSearch(overrideType = null, overrideIndex = null) {
    const query = document.getElementById('searchInput').value.trim();
    if(!query) return;

    const loader = document.getElementById('loader');
    const wrapper = document.getElementById('resultsWrapper');
    const errorMsg = document.getElementById('errorMsg');
    
    // Ocultar modal si existe
    closeModal();

    wrapper.classList.add('hidden');
    errorMsg.classList.add('hidden');
    loader.classList.remove('hidden');

    try {
        const payload = {
            query: query,
            mode: currentMode
        };
        if(overrideType) payload.override_type = overrideType;
        if(overrideIndex !== null) payload.override_index = overrideIndex;

        const response = await fetch('/api/recommend', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if(data.status === 'success') {
            renderCards(data.data);
            if(data.chart_data && Object.keys(data.chart_data).length > 0) {
                renderChart(data.chart_data);
            }
            wrapper.classList.remove('hidden');
        } else if (data.status === 'conflict') {
            showConflictModal(data);
        } else {
            errorMsg.textContent = data.message;
            errorMsg.classList.remove('hidden');
        }
    } catch (err) {
        errorMsg.textContent = "❌ Error de conexión. ¿Está corriendo el servidor FastAPI?";
        errorMsg.classList.remove('hidden');
    } finally {
        loader.classList.add('hidden');
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
