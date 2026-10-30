const ALLOC_COLORS = ['#2563b8', '#2e9e58', '#c53030', '#d97706', '#718096', '#7c3aed'];

let perfChart = null;

function initPerfChart(labels, values) {
    const ctx = document.getElementById('perfChart').getContext('2d');
    perfChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                borderColor: '#2a5cb8',
                backgroundColor: 'rgba(42, 92, 184, 0.10)',
                borderWidth: 1.5,
                fill: true,
                tension: 0.35,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: '#2a5cb8',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(20,40,80,0.88)',
                    titleFont: { size: 10, family: 'Arial' },
                    bodyFont: { size: 11, family: 'Arial' },
                    callbacks: {
                        label: ctx => ' $' + ctx.raw.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
                    }
                }
            },
            scales: {
                x: {
                    ticks: { font: { size: 10, family: 'Arial' }, maxTicksLimit: 10, color: '#445' },
                    grid: { color: '#dde4ee' },
                },
                y: {
                    ticks: {
                        font: { size: 10, family: 'Arial' },
                        color: '#445',
                        callback: v => '$' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v),
                    },
                    grid: { color: '#dde4ee' },
                }
            }
        }
    });
}

function initAllocChart(labels, values) {
    const colors = ALLOC_COLORS.slice(0, labels.length);
    const ctx = document.getElementById('allocChart').getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 1.5,
                borderColor: '#ffffff',
            }]
        },
        options: {
            cutout: '64%',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(20,40,80,0.88)',
                    callbacks: {
                        label: ctx => ' ' + ctx.label + ': ' + ctx.raw.toFixed(1) + '%',
                    }
                }
            }
        }
    });
}

function switchPeriod(period) {
    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector('[data-period="' + period + '"]');
    if (btn) btn.classList.add('active');

    fetch('/api/chart-data?period=' + period)
        .then(r => r.json())
        .then(data => {
            if (!perfChart) return;
            perfChart.data.labels = data.labels;
            perfChart.data.datasets[0].data = data.values;
            perfChart.update();
        });
}
