/**
 * Carbon Ledger - Interactive Visualization & UI Engine
 * Chart.js 4.x integrations, real-time emission calculations, and net-zero scenario simulations.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Live Emission Calculator in Add/Edit Data forms
    const categorySelect = document.getElementById('activity-category-select');
    const activityInput = document.getElementById('activity-quantity-input');
    const unitSelect = document.getElementById('activity-unit-select');
    const livePreviewBox = document.getElementById('live-calc-preview');
    const liveCo2eSpan = document.getElementById('preview-co2e-val');
    const liveFactorSpan = document.getElementById('preview-factor-val');

    function updateLiveCalculation() {
        if (!categorySelect || !activityInput) return;
        const category = categorySelect.value;
        const activity = parseFloat(activityInput.value);
        const unit = unitSelect ? unitSelect.value : '';

        if (!category || isNaN(activity) || activity <= 0) {
            if (livePreviewBox) livePreviewBox.style.display = 'none';
            return;
        }

        fetch('/api/calculate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: category, activity: activity, unit: unit })
        })
        .then(response => {
            if (!response.ok) throw new Error('Calculation error');
            return response.json();
        })
        .then(data => {
            if (livePreviewBox && liveCo2eSpan) {
                liveCo2eSpan.textContent = `${data.co2e.toLocaleString()} kg CO2e (${data.co2e_tonnes} tonnes)`;
                if (liveFactorSpan) {
                    liveFactorSpan.textContent = `Applied Factor: ${data.emission_factor} ${data.factor_unit} [${data.source}]`;
                }
                livePreviewBox.style.display = 'block';
            }
        })
        .catch(() => {
            if (livePreviewBox) livePreviewBox.style.display = 'none';
        });
    }

    if (categorySelect && activityInput) {
        categorySelect.addEventListener('change', updateLiveCalculation);
        activityInput.addEventListener('input', updateLiveCalculation);
        if (unitSelect) unitSelect.addEventListener('change', updateLiveCalculation);
    }

    // 2. Dashboard Charts Initialization
    const categoryChartElem = document.getElementById('categoryChart');
    if (categoryChartElem) {
        fetch('/api/category-emissions')
            .then(res => res.json())
            .then(result => {
                if (!result.labels || result.labels.length === 0) return;
                
                const institutionalPalette = [
                    '#004f98', '#0d9488', '#0b2545', '#d97706', 
                    '#475569', '#2563eb', '#15803d', '#dc2626'
                ];

                new Chart(categoryChartElem.getContext('2d'), {
                    type: 'doughnut',
                    data: {
                        labels: result.labels.map(l => l.replace(/_/g, ' ').toUpperCase()),
                        datasets: [{
                            data: result.data,
                            backgroundColor: institutionalPalette.slice(0, result.labels.length),
                            borderWidth: 1,
                            borderColor: '#ffffff'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    font: { family: "'Inter', sans-serif", size: 11 },
                                    boxWidth: 12,
                                    padding: 12
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function (ctx) {
                                        const val = ctx.parsed || 0;
                                        return ` ${ctx.label}: ${val.toLocaleString()} kg CO2e`;
                                    }
                                }
                            }
                        },
                        cutout: '62%'
                    }
                });
            });
    }

    const monthlyChartElem = document.getElementById('monthlyChart');
    if (monthlyChartElem) {
        fetch('/api/monthly-emissions')
            .then(res => res.json())
            .then(result => {
                if (!result.labels || result.labels.length === 0) return;

                new Chart(monthlyChartElem.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: result.labels,
                        datasets: [{
                            label: 'Emissions (kg CO2e)',
                            data: result.data,
                            borderColor: '#004f98',
                            backgroundColor: 'rgba(0, 79, 152, 0.08)',
                            fill: true,
                            tension: 0.15,
                            pointBackgroundColor: '#004f98',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 1.5,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                grid: { color: '#f1f5f9' },
                                ticks: {
                                    font: { family: "'Inter', sans-serif", size: 10 },
                                    callback: function (val) { return val.toLocaleString() + ' kg'; }
                                }
                            },
                            x: {
                                grid: { display: false },
                                ticks: { font: { family: "'Inter', sans-serif", size: 10 } }
                            }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: function (ctx) {
                                        const kg = ctx.parsed.y;
                                        const tonnes = (kg / 1000).toFixed(3);
                                        return ` ${kg.toLocaleString()} kg CO2e (${tonnes} tonnes)`;
                                    }
                                }
                            }
                        }
                    }
                });
            });
    }

    // 3. Interactive Scenario Simulation Sliders in Net-Zero page
    const elecSlider = document.getElementById('sim-elec-slider');
    const fuelSlider = document.getElementById('sim-fuel-slider');
    const transSlider = document.getElementById('sim-trans-slider');
    
    if (elecSlider && fuelSlider && transSlider) {
        function triggerScenarioSimulation() {
            const baseElec = parseFloat(document.getElementById('base-elec-val').value) || 0;
            const baseFuel = parseFloat(document.getElementById('base-fuel-val').value) || 0;
            const baseTrans = parseFloat(document.getElementById('base-trans-val').value) || 0;
            const baseOther = parseFloat(document.getElementById('base-other-val').value) || 0;

            const targetPct = parseFloat(document.getElementById('sim-target-pct').value) || 50;
            const targetYear = parseInt(document.getElementById('sim-target-year').value) || 2030;

            const elecR = parseFloat(elecSlider.value) || 0;
            const fuelR = parseFloat(fuelSlider.value) || 0;
            const transR = parseFloat(transSlider.value) || 0;

            document.getElementById('sim-elec-display').textContent = `${elecR}%`;
            document.getElementById('sim-fuel-display').textContent = `${fuelR}%`;
            document.getElementById('sim-trans-display').textContent = `${transR}%`;

            fetch('/api/simulate-scenario', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base_dict: {
                        electricity: baseElec,
                        fuel: baseFuel,
                        transportation: baseTrans,
                        other: baseOther
                    },
                    target_pct: targetPct,
                    target_year: targetYear,
                    elec_reduction: elecR,
                    fuel_reduction: fuelR,
                    transport_reduction: transR
                })
            })
            .then(r => r.json())
            .then(sim => {
                document.getElementById('scenario-result-co2e').textContent = `${sim.scenario_total_kg.toLocaleString()} kg`;
                document.getElementById('scenario-result-tonnes').textContent = `(${sim.scenario_total_t} tonnes CO2e)`;
                document.getElementById('scenario-savings-val').textContent = `${sim.savings_kg.toLocaleString()} kg CO2e (${sim.savings_pct}%)`;
                document.getElementById('scenario-gap-val').textContent = `${sim.remaining_gap_kg.toLocaleString()} kg CO2e`;

                const statusBadge = document.getElementById('scenario-status-badge');
                if (statusBadge) {
                    if (sim.target_achieved) {
                        statusBadge.className = 'badge bg-success';
                        statusBadge.textContent = 'TARGET ACHIEVED';
                    } else {
                        statusBadge.className = 'badge bg-warning text-dark';
                        statusBadge.textContent = 'GAP TO TARGET';
                    }
                }
            });
        }

        elecSlider.addEventListener('input', triggerScenarioSimulation);
        fuelSlider.addEventListener('input', triggerScenarioSimulation);
        transSlider.addEventListener('input', triggerScenarioSimulation);
    }
});
