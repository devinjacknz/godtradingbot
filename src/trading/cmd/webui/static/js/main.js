// Utility functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatNumber(number, decimals = 2) {
    return number.toFixed(decimals);
}

function formatPercentage(number) {
    return `${formatNumber(number * 100)}%`;
}

function formatCurrency(number) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(number);
}

// Chart configuration
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'top',
        },
        tooltip: {
            mode: 'index',
            intersect: false,
        }
    }
};

// Create equity curve chart
function createEquityChart(containerId, data) {
    const ctx = document.getElementById(containerId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(point => formatDate(point.time)),
            datasets: [{
                label: 'Portfolio Value',
                data: data.map(point => point.value),
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day'
                    }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: value => formatCurrency(value)
                    }
                }
            }
        }
    });
}

// Create monthly returns chart
function createMonthlyReturnsChart(containerId, data) {
    const ctx = document.getElementById(containerId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(point => point.month),
            datasets: [{
                label: 'Monthly Return',
                data: data.map(point => point.return * 100),
                backgroundColor: data.map(point => 
                    point.return >= 0 ? 'rgba(75, 192, 192, 0.5)' : 'rgba(255, 99, 132, 0.5)'
                ),
                borderColor: data.map(point => 
                    point.return >= 0 ? 'rgb(75, 192, 192)' : 'rgb(255, 99, 132)'
                ),
                borderWidth: 1
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: {
                    ticks: {
                        callback: value => `${value}%`
                    }
                }
            }
        }
    });
}

// Create drawdown chart
function createDrawdownChart(containerId, data) {
    const ctx = document.getElementById(containerId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(point => formatDate(point.time)),
            datasets: [{
                label: 'Drawdown',
                data: data.map(point => point.drawdown * 100),
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                borderWidth: 2,
                fill: true
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: {
                    ticks: {
                        callback: value => `${value}%`
                    }
                }
            }
        }
    });
}

// Create trade distribution chart
function createTradeDistributionChart(containerId, data) {
    const ctx = document.getElementById(containerId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(point => `${point.min} to ${point.max}`),
            datasets: [{
                label: 'Number of Trades',
                data: data.map(point => point.count),
                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                borderColor: 'rgb(75, 192, 192)',
                borderWidth: 1
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

// Update metrics display
function updateMetrics(metrics) {
    const metricsContainer = document.querySelector('.metrics-grid');
    if (!metricsContainer) return;

    const metricElements = {
        totalReturn: formatPercentage(metrics.totalReturn),
        winRate: formatPercentage(metrics.winRate),
        sharpeRatio: formatNumber(metrics.sharpeRatio),
        maxDrawdown: formatPercentage(metrics.maxDrawdown),
        profitFactor: formatNumber(metrics.profitFactor),
        averageTrade: formatCurrency(metrics.averageTrade),
        totalTrades: metrics.totalTrades,
        averageHoldingTime: `${metrics.averageHoldingTime} days`
    };

    Object.entries(metricElements).forEach(([key, value]) => {
        const element = metricsContainer.querySelector(`[data-metric="${key}"]`);
        if (element) {
            element.textContent = value;
        }
    });
}

// Update trades table
function updateTradesTable(trades) {
    const tableBody = document.querySelector('#trades-table tbody');
    if (!tableBody) return;

    tableBody.innerHTML = trades.map(trade => `
        <tr>
            <td>${formatDate(trade.time)}</td>
            <td>${trade.type}</td>
            <td>${formatCurrency(trade.price)}</td>
            <td>${formatNumber(trade.size, 4)}</td>
            <td class="${trade.pnl >= 0 ? 'profit' : 'loss'}">${formatCurrency(trade.pnl)}</td>
        </tr>
    `).join('');
}

// Initialize charts and data on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if we're on the result details page
    const resultId = document.body.dataset.resultId;
    if (resultId) {
        fetch(`/api/result/${resultId}`)
            .then(response => response.json())
            .then(result => {
                updateMetrics(result.metrics);
                createEquityChart('equity-chart', result.equityCurve);
                createMonthlyReturnsChart('monthly-returns-chart', result.monthlyReturns);
                createDrawdownChart('drawdown-chart', result.drawdowns);
                createTradeDistributionChart('trade-distribution-chart', result.tradeDistribution);
                updateTradesTable(result.trades);
            })
            .catch(error => console.error('Error loading result data:', error));
    }

    // Check if we're on the results list page
    const recentResultsContainer = document.getElementById('recent-results');
    if (recentResultsContainer) {
        fetch('/api/results')
            .then(response => response.json())
            .then(results => {
                recentResultsContainer.innerHTML = results.map(result => `
                    <div class="result-card">
                        <h3>${result.symbol}</h3>
                        <p>Total Return: ${formatPercentage(result.totalReturn)}</p>
                        <p>Win Rate: ${formatPercentage(result.winRate)}</p>
                        <p>Sharpe Ratio: ${formatNumber(result.sharpeRatio)}</p>
                        <a href="/result/${result.id}">View Details</a>
                    </div>
                `).join('');
            })
            .catch(error => console.error('Error loading results:', error));
    }
}); 