from expense_analyzer.dashboard.styles import configure_page
from expense_analyzer.dashboard.app import ExpenseDashboard

configure_page()

app = ExpenseDashboard()
app.render()