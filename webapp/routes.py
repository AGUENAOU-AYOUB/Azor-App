from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    Response,
    flash,
)
import os
import json

from .jobqueue import enqueue, stream

main_bp = Blueprint('main', __name__)

SCRIPTS = {
    'percentage': os.path.join('scripts', 'update_prices_shopify.py'),
    'variant': os.path.join('tempo solution', 'update_prices.py')
}


def login_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped

@main_bp.route('/')
@login_required
def home():
    return render_template('home.html')

@main_bp.route('/percentage-updater')
@login_required
def percentage_updater():
    return render_template('percentage.html')

@main_bp.route('/variant-updater', methods=['GET', 'POST'])
@login_required
def variant_updater():
    file_path = os.path.join('tempo solution', 'variant_prices.json')
    with open(file_path, encoding='utf-8') as f:
        surcharges = json.load(f)

    if request.method == 'POST':
        updated = {cat: {} for cat in surcharges}
        for cat, chains in surcharges.items():
            for chain in chains:
                key = f"{cat}_{chain.replace(' ', '_')}"
                val = request.form.get(key, '').strip()
                try:
                    updated[cat][chain] = float(val)
                except ValueError:
                    flash(f"Invalid value for {chain}", 'error')
                    return render_template('variant.html', surcharges=surcharges)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(updated, f, indent=2)
        surcharges = updated
        flash('Surcharges saved.', 'success')

    return render_template('variant.html', surcharges=surcharges)


def stream_job(cmd):
    job_id = enqueue(cmd)

    def generator():
        for line in stream(job_id):
            yield f"data: {line}\n\n"
        yield "data: --done--\n\n"

    return generator()

@main_bp.route('/stream/percentage')
@login_required
def stream_percentage():
    percent = request.args.get('percent')
    if not percent:
        return 'Missing percent', 400
    cmd = ['python3', SCRIPTS['percentage'], '--percent', percent]
    return Response(stream_job(cmd), mimetype='text/event-stream')

@main_bp.route('/stream/variant')
@login_required
def stream_variant():
    cmd = ['python3', SCRIPTS['variant']]
    return Response(stream_job(cmd), mimetype='text/event-stream')
