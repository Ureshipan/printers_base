"""Blueprint: HTML-страницы приложения."""
from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return render_template('dashboard.html')


@pages_bp.route('/printer-control')
def printer_control():
    return render_template('printer-control.html')


@pages_bp.route('/planning')
def planning():
    return render_template('planning.html')


@pages_bp.route('/maintenance')
def maintenance():
    return render_template('maintenance.html')


@pages_bp.route('/spools')
def spools():
    return render_template('spools.html')
