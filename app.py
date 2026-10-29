import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from blanko_service import generate_blanko_combined, parse_blanko_combined
from config import Config
from db import execute, query_all, query_one
from helpers import (
    TARGET_MAP,
    hitung_progress,
    predikat_dari_nilai,
    predikat_huruf,
)
from parent_service import (
    ensure_parent_account,
    get_children_of_parent,
    get_default_parent_password,
    parent_owns_siswa,
    reset_all_parent_passwords_to_default,
    reset_parent_password,
    set_default_parent_password,
)

app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.BLANKO_FOLDER, exist_ok=True)


# ─── Auth helpers ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Akses khusus administrator.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)

    return wrapped


def staff_required(f):
    """Hanya admin & musyrif (bukan orang tua)."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") == "orang_tua":
            flash("Halaman ini khusus staf sekolah.", "warning")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)

    return wrapped


def is_parent():
    return session.get("role") == "orang_tua"


def get_tahun_aktif():
    return query_one("SELECT * FROM tahun_ajaran WHERE aktif=1 LIMIT 1")


def get_tahun_by_id(ta_id):
    return query_one("SELECT * FROM tahun_ajaran WHERE id=%s", (ta_id,))


def current_ta_id():
    """Tahun ajaran yang sedang dipilih di session, fallback ke aktif."""
    ta_id = session.get("ta_id")
    if ta_id:
        ta = get_tahun_by_id(ta_id)
        if ta:
            return ta
    return get_tahun_aktif()


@app.context_processor
def inject_globals():
    ta = None
    try:
        ta = current_ta_id()
    except Exception:
        ta = None
    return {
        "school_name": Config.SCHOOL_NAME,
        "app_title": Config.APP_TITLE,
        "current_ta": ta,
        "tahun_list": _safe_tahun_list(),
        "now": datetime.now(),
    }


def _safe_tahun_list():
    try:
        return query_all("SELECT * FROM tahun_ajaran ORDER BY nama DESC")
    except Exception:
        return []


# ─── Auth ─────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        # Username orang tua = nama (case-insensitive)
        user = query_one(
            "SELECT * FROM users WHERE LOWER(username)=LOWER(%s) AND aktif=1",
            (username,),
        )
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["nama"] = user["nama_lengkap"]
            session["role"] = user["role"]
            session["must_change_password"] = bool(user.get("must_change_password"))
            ta = get_tahun_aktif()
            if ta:
                session["ta_id"] = ta["id"]
            flash(f"Selamat datang, {user['nama_lengkap']}.", "success")
            if user["role"] == "orang_tua" and user.get("must_change_password"):
                flash(
                    "Anda masih memakai password default. Disarankan mengganti password.",
                    "warning",
                )
                return redirect(url_for("ganti_password"))
            return redirect(url_for("dashboard"))
        flash("Username atau password salah.", "danger")
    try:
        default_pw = get_default_parent_password()
    except Exception:
        default_pw = Config.PARENT_DEFAULT_PASSWORD
    return render_template("login.html", parent_default_password=default_pw)


@app.route("/logout")
def logout():
    session.clear()
    flash("Anda telah keluar.", "info")
    return redirect(url_for("login"))


@app.route("/set-tahun/<int:ta_id>")
@login_required
def set_tahun(ta_id):
    ta = get_tahun_by_id(ta_id)
    if ta:
        session["ta_id"] = ta["id"]
        flash(f"Tahun ajaran diganti ke {ta['nama']} (Sem {ta['semester']}).", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/ganti-password", methods=["GET", "POST"])
@login_required
def ganti_password():
    if request.method == "POST":
        lama = request.form.get("password_lama", "")
        baru = request.form.get("password_baru", "")
        konfirmasi = request.form.get("password_konfirmasi", "")
        user = query_one("SELECT * FROM users WHERE id=%s", (session["user_id"],))
        if not user or not check_password_hash(user["password_hash"], lama):
            flash("Password lama tidak sesuai.", "danger")
        elif len(baru) < 6:
            flash("Password baru minimal 6 karakter.", "danger")
        elif baru != konfirmasi:
            flash("Konfirmasi password tidak cocok.", "danger")
        else:
            execute(
                "UPDATE users SET password_hash=%s, must_change_password=0 WHERE id=%s",
                (generate_password_hash(baru), session["user_id"]),
            )
            session["must_change_password"] = False
            flash("Password berhasil diubah.", "success")
            return redirect(url_for("dashboard"))
    return render_template("ganti_password.html")


# ─── Dashboard ────────────────────────────────────────────────
@app.route("/")
@login_required
def dashboard():
    ta = current_ta_id()
    if not ta:
        if is_parent():
            flash("Belum ada tahun ajaran aktif.", "warning")
            return render_template("parent_dashboard.html", anak_list=[], setoran_terbaru=[])
        flash("Belum ada tahun ajaran. Silakan buat terlebih dahulu.", "warning")
        return redirect(url_for("tahun_ajaran"))

    # Dashboard khusus orang tua: hanya anaknya
    if is_parent():
        return _parent_dashboard(ta)

    stats = {
        "siswa": query_one(
            "SELECT COUNT(*) AS n FROM siswa WHERE tahun_ajaran_id=%s AND aktif=1",
            (ta["id"],),
        )["n"],
        "kelas": query_one(
            "SELECT COUNT(*) AS n FROM kelas WHERE tahun_ajaran_id=%s AND aktif=1",
            (ta["id"],),
        )["n"],
        "musyrif": query_one(
            "SELECT COUNT(*) AS n FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1",
            (ta["id"],),
        )["n"],
        "setoran_hari_ini": query_one(
            "SELECT COUNT(*) AS n FROM setoran WHERE tahun_ajaran_id=%s AND DATE(tanggal)=CURDATE()",
            (ta["id"],),
        )["n"],
    }

    setoran_terbaru = query_all(
        """
        SELECT st.*, s.nama AS nama_siswa, k.nama AS nama_kelas, m.nama AS nama_musyrif
        FROM setoran st
        JOIN siswa s ON s.id = st.siswa_id
        JOIN kelas k ON k.id = s.kelas_id
        LEFT JOIN musyrif m ON m.id = st.musyrif_id
        WHERE st.tahun_ajaran_id=%s
        ORDER BY st.tanggal DESC
        LIMIT 10
        """,
        (ta["id"],),
    )

    progress_kelas = query_all(
        """
        SELECT k.id, k.nama, k.jenjang,
               COUNT(DISTINCT s.id) AS jml_siswa,
               COALESCE(SUM(CASE WHEN st.status='Lulus' AND st.jenis='Ziyadah'
                                 THEN st.volume_halaman ELSE 0 END), 0) AS total_halaman
        FROM kelas k
        LEFT JOIN siswa s ON s.kelas_id = k.id AND s.aktif=1
        LEFT JOIN setoran st ON st.siswa_id = s.id AND st.tahun_ajaran_id = k.tahun_ajaran_id
        WHERE k.tahun_ajaran_id=%s AND k.aktif=1
        GROUP BY k.id
        ORDER BY k.jenjang, k.nama
        """,
        (ta["id"],),
    )
    for row in progress_kelas:
        # rata-rata per siswa di kelas
        avg_hal = (row["total_halaman"] / row["jml_siswa"]) if row["jml_siswa"] else 0
        row["progress"] = hitung_progress(avg_hal, row["jenjang"], ta["semester"])

    return render_template(
        "dashboard.html",
        stats=stats,
        setoran_terbaru=setoran_terbaru,
        progress_kelas=progress_kelas,
        target_map=TARGET_MAP,
    )


def _parent_dashboard(ta):
    anak_list = get_children_of_parent(session["user_id"], ta["id"])
    for anak in anak_list:
        total = query_one(
            """
            SELECT COALESCE(SUM(CASE WHEN status='Lulus' AND jenis='Ziyadah'
                                     THEN volume_halaman ELSE 0 END), 0) AS total_halaman
            FROM setoran WHERE siswa_id=%s AND tahun_ajaran_id=%s
            """,
            (anak["id"], ta["id"]),
        )
        anak["progress"] = hitung_progress(
            total["total_halaman"], anak["jenjang"], ta["semester"]
        )

    anak_ids = [a["id"] for a in anak_list] or [0]
    placeholders = ",".join(["%s"] * len(anak_ids))
    setoran_terbaru = query_all(
        f"""
        SELECT st.*, s.nama AS nama_siswa, k.nama AS nama_kelas
        FROM setoran st
        JOIN siswa s ON s.id = st.siswa_id
        JOIN kelas k ON k.id = s.kelas_id
        WHERE st.siswa_id IN ({placeholders}) AND st.tahun_ajaran_id=%s
        ORDER BY st.tanggal DESC
        LIMIT 15
        """,
        (*anak_ids, ta["id"]),
    )
    return render_template(
        "parent_dashboard.html",
        anak_list=anak_list,
        setoran_terbaru=setoran_terbaru,
    )


# ─── Tahun Ajaran ─────────────────────────────────────────────
@app.route("/tahun-ajaran", methods=["GET", "POST"])
@admin_required
def tahun_ajaran():
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        semester = request.form.get("semester", "1")
        if not nama:
            flash("Nama tahun ajaran wajib diisi.", "danger")
        else:
            try:
                execute(
                    "INSERT INTO tahun_ajaran (nama, semester, aktif) VALUES (%s,%s,0)",
                    (nama, semester),
                )
                flash(f"Tahun ajaran {nama} ditambahkan.", "success")
            except Exception as e:
                flash(f"Gagal menambah: {e}", "danger")
        return redirect(url_for("tahun_ajaran"))

    daftar = query_all("SELECT * FROM tahun_ajaran ORDER BY nama DESC")
    return render_template("tahun_ajaran.html", daftar=daftar)


@app.route("/tahun-ajaran/<int:ta_id>/aktifkan")
@admin_required
def aktifkan_tahun(ta_id):
    execute("UPDATE tahun_ajaran SET aktif=0")
    execute("UPDATE tahun_ajaran SET aktif=1 WHERE id=%s", (ta_id,))
    session["ta_id"] = ta_id
    ta = get_tahun_by_id(ta_id)
    flash(f"Tahun ajaran aktif: {ta['nama']}.", "success")
    return redirect(url_for("tahun_ajaran"))


@app.route("/tahun-ajaran/<int:ta_id>/semester", methods=["POST"])
@admin_required
def update_semester(ta_id):
    semester = request.form.get("semester", "1")
    execute("UPDATE tahun_ajaran SET semester=%s WHERE id=%s", (semester, ta_id))
    flash("Semester diperbarui.", "success")
    return redirect(url_for("tahun_ajaran"))


# ─── Musyrif ──────────────────────────────────────────────────
@app.route("/musyrif")
@staff_required
def musyrif_list():
    ta = current_ta_id()
    if not ta:
        return redirect(url_for("tahun_ajaran"))
    daftar = query_all(
        """
        SELECT m.*,
               (SELECT COUNT(*) FROM siswa s WHERE s.musyrif_id=m.id AND s.aktif=1) AS jml_siswa
        FROM musyrif m
        WHERE m.tahun_ajaran_id=%s
        ORDER BY m.nama
        """,
        (ta["id"],),
    )
    return render_template("musyrif_list.html", daftar=daftar)


@app.route("/musyrif/tambah", methods=["GET", "POST"])
@admin_required
def musyrif_tambah():
    ta = current_ta_id()
    if request.method == "POST":
        kode = request.form.get("kode", "").strip()
        nama = request.form.get("nama", "").strip()
        gelar = request.form.get("gelar", "").strip() or None
        telepon = request.form.get("telepon", "").strip() or None
        if not kode or not nama:
            flash("Kode dan nama wajib diisi.", "danger")
        else:
            try:
                execute(
                    "INSERT INTO musyrif (kode, nama, gelar, telepon, tahun_ajaran_id) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (kode, nama, gelar, telepon, ta["id"]),
                )
                flash("Musyrif berhasil ditambahkan.", "success")
                return redirect(url_for("musyrif_list"))
            except Exception as e:
                flash(f"Gagal: {e}", "danger")
    return render_template("musyrif_form.html", item=None)


@app.route("/musyrif/<int:mid>/edit", methods=["GET", "POST"])
@admin_required
def musyrif_edit(mid):
    item = query_one("SELECT * FROM musyrif WHERE id=%s", (mid,))
    if not item:
        flash("Data tidak ditemukan.", "danger")
        return redirect(url_for("musyrif_list"))
    if request.method == "POST":
        try:
            execute(
                "UPDATE musyrif SET kode=%s, nama=%s, gelar=%s, telepon=%s, aktif=%s WHERE id=%s",
                (
                    request.form.get("kode", "").strip(),
                    request.form.get("nama", "").strip(),
                    request.form.get("gelar", "").strip() or None,
                    request.form.get("telepon", "").strip() or None,
                    1 if request.form.get("aktif") == "1" else 0,
                    mid,
                ),
            )
            flash("Data musyrif diperbarui.", "success")
            return redirect(url_for("musyrif_list"))
        except Exception as e:
            flash(f"Gagal: {e}", "danger")
    return render_template("musyrif_form.html", item=item)


@app.route("/musyrif/<int:mid>/hapus", methods=["POST"])
@admin_required
def musyrif_hapus(mid):
    execute("DELETE FROM musyrif WHERE id=%s", (mid,))
    flash("Musyrif dihapus.", "info")
    return redirect(url_for("musyrif_list"))


# ─── Kelas ────────────────────────────────────────────────────
@app.route("/kelas")
@staff_required
def kelas_list():
    ta = current_ta_id()
    if not ta:
        return redirect(url_for("tahun_ajaran"))
    daftar = query_all(
        """
        SELECT k.*, m.nama AS nama_musyrif,
               (SELECT COUNT(*) FROM siswa s WHERE s.kelas_id=k.id AND s.aktif=1) AS jml_siswa
        FROM kelas k
        LEFT JOIN musyrif m ON m.id = k.musyrif_id
        WHERE k.tahun_ajaran_id=%s
        ORDER BY k.jenjang, k.nama
        """,
        (ta["id"],),
    )
    return render_template("kelas_list.html", daftar=daftar)


@app.route("/kelas/tambah", methods=["GET", "POST"])
@admin_required
def kelas_tambah():
    ta = current_ta_id()
    musyrif = query_all(
        "SELECT * FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY nama",
        (ta["id"],),
    )
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        jenjang = int(request.form.get("jenjang", 7))
        musyrif_id = request.form.get("musyrif_id") or None
        try:
            execute(
                "INSERT INTO kelas (nama, jenjang, tahun_ajaran_id, musyrif_id) VALUES (%s,%s,%s,%s)",
                (nama, jenjang, ta["id"], musyrif_id),
            )
            flash("Kelas berhasil ditambahkan.", "success")
            return redirect(url_for("kelas_list"))
        except Exception as e:
            flash(f"Gagal: {e}", "danger")
    return render_template("kelas_form.html", item=None, musyrif=musyrif)


@app.route("/kelas/<int:kid>/edit", methods=["GET", "POST"])
@admin_required
def kelas_edit(kid):
    ta = current_ta_id()
    item = query_one("SELECT * FROM kelas WHERE id=%s", (kid,))
    musyrif = query_all(
        "SELECT * FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY nama",
        (ta["id"],),
    )
    if not item:
        flash("Kelas tidak ditemukan.", "danger")
        return redirect(url_for("kelas_list"))
    if request.method == "POST":
        try:
            execute(
                "UPDATE kelas SET nama=%s, jenjang=%s, musyrif_id=%s, aktif=%s WHERE id=%s",
                (
                    request.form.get("nama", "").strip(),
                    int(request.form.get("jenjang", 7)),
                    request.form.get("musyrif_id") or None,
                    1 if request.form.get("aktif") == "1" else 0,
                    kid,
                ),
            )
            flash("Kelas diperbarui.", "success")
            return redirect(url_for("kelas_list"))
        except Exception as e:
            flash(f"Gagal: {e}", "danger")
    return render_template("kelas_form.html", item=item, musyrif=musyrif)


@app.route("/kelas/<int:kid>/hapus", methods=["POST"])
@admin_required
def kelas_hapus(kid):
    try:
        execute("DELETE FROM kelas WHERE id=%s", (kid,))
        flash("Kelas dihapus.", "info")
    except Exception as e:
        flash(f"Tidak bisa dihapus (mungkin masih ada siswa): {e}", "danger")
    return redirect(url_for("kelas_list"))


# ─── Siswa ────────────────────────────────────────────────────
@app.route("/siswa")
@staff_required
def siswa_list():
    ta = current_ta_id()
    if not ta:
        return redirect(url_for("tahun_ajaran"))
    q = request.args.get("q", "").strip()
    kelas_id = request.args.get("kelas_id", "")
    musyrif_id = request.args.get("musyrif_id", "")
    sql = """
        SELECT s.*, k.nama AS nama_kelas, k.jenjang, m.nama AS nama_musyrif, m.kode AS kode_musyrif,
               u.username AS nama_orang_tua
        FROM siswa s
        JOIN kelas k ON k.id = s.kelas_id
        LEFT JOIN musyrif m ON m.id = s.musyrif_id
        LEFT JOIN users u ON u.id = s.orang_tua_user_id
        WHERE s.tahun_ajaran_id=%s
    """
    params = [ta["id"]]
    if q:
        sql += " AND (s.nama LIKE %s OR s.nis LIKE %s OR u.username LIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if kelas_id:
        sql += " AND s.kelas_id=%s"
        params.append(kelas_id)
    if musyrif_id == "0":
        sql += " AND s.musyrif_id IS NULL"
    elif musyrif_id:
        sql += " AND s.musyrif_id=%s"
        params.append(musyrif_id)
    sql += " ORDER BY k.jenjang, k.nama, s.nama"
    daftar = query_all(sql, params)
    kelas = query_all(
        "SELECT * FROM kelas WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY jenjang, nama",
        (ta["id"],),
    )
    musyrif = query_all(
        "SELECT * FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY nama",
        (ta["id"],),
    )
    return render_template(
        "siswa_list.html",
        daftar=daftar,
        kelas=kelas,
        musyrif=musyrif,
        q=q,
        kelas_id=kelas_id,
        musyrif_id=musyrif_id,
    )


@app.route("/siswa/pindah-musyrif", methods=["GET", "POST"])
@admin_required
def siswa_pindah_musyrif():
    ta = current_ta_id()
    if not ta:
        return redirect(url_for("tahun_ajaran"))

    musyrif = query_all(
        "SELECT * FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY nama",
        (ta["id"],),
    )

    if request.method == "POST":
        raw_target = request.form.get("musyrif_tujuan", "")
        if raw_target in ("", "0"):
            target_id = None
        else:
            target_id = raw_target
        siswa_ids = request.form.getlist("siswa_ids")
        if not siswa_ids:
            flash("Pilih minimal satu siswa.", "warning")
            return redirect(url_for("siswa_pindah_musyrif"))
        if not raw_target:
            flash("Pilih musyrif tujuan.", "warning")
            return redirect(
                url_for("siswa_pindah_musyrif", dari=request.form.get("dari", ""))
            )
        if target_id:
            target = query_one(
                "SELECT * FROM musyrif WHERE id=%s AND tahun_ajaran_id=%s",
                (target_id, ta["id"]),
            )
            if not target:
                flash("Musyrif tujuan tidak valid.", "danger")
                return redirect(url_for("siswa_pindah_musyrif"))
        placeholders = ",".join(["%s"] * len(siswa_ids))
        execute(
            f"UPDATE siswa SET musyrif_id=%s "
            f"WHERE id IN ({placeholders}) AND tahun_ajaran_id=%s",
            (target_id, *siswa_ids, ta["id"]),
        )
        tujuan_nama = (
            query_one("SELECT nama FROM musyrif WHERE id=%s", (target_id,))["nama"]
            if target_id
            else "Tanpa musyrif"
        )
        flash(
            f"{len(siswa_ids)} siswa dipindahkan ke musyrif: {tujuan_nama}.",
            "success",
        )
        return redirect(url_for("siswa_list", musyrif_id=target_id or "0"))

    dari = request.args.get("dari", "")
    sql = """
        SELECT s.id, s.nis, s.nama, k.nama AS nama_kelas, m.nama AS nama_musyrif, m.id AS mid
        FROM siswa s
        JOIN kelas k ON k.id = s.kelas_id
        LEFT JOIN musyrif m ON m.id = s.musyrif_id
        WHERE s.tahun_ajaran_id=%s AND s.aktif=1
    """
    params = [ta["id"]]
    if dari == "0":
        sql += " AND s.musyrif_id IS NULL"
    elif dari:
        sql += " AND s.musyrif_id=%s"
        params.append(dari)
    sql += " ORDER BY m.nama, k.nama, s.nama"
    daftar = query_all(sql, params)
    return render_template(
        "siswa_pindah_musyrif.html",
        daftar=daftar,
        musyrif=musyrif,
        dari=dari,
    )


@app.route("/siswa/tambah", methods=["GET", "POST"])
@admin_required
def siswa_tambah():
    ta = current_ta_id()
    kelas = query_all(
        "SELECT * FROM kelas WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY jenjang, nama",
        (ta["id"],),
    )
    musyrif = query_all(
        "SELECT * FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY nama",
        (ta["id"],),
    )
    if request.method == "POST":
        try:
            ortu_id = ensure_parent_account(
                request.form.get("nama_orang_tua", ""),
                request.form.get("telepon_orang_tua") or None,
            )
            execute(
                "INSERT INTO siswa (nis, nama, jenis_kelamin, kelas_id, musyrif_id, "
                "orang_tua_user_id, tahun_ajaran_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    request.form.get("nis", "").strip(),
                    request.form.get("nama", "").strip(),
                    request.form.get("jenis_kelamin", "L"),
                    request.form.get("kelas_id"),
                    request.form.get("musyrif_id") or None,
                    ortu_id,
                    ta["id"],
                ),
            )
            flash("Siswa berhasil ditambahkan.", "success")
            if ortu_id:
                flash(
                    f"Akun orang tua siap. Username: nama orang tua · "
                    f"Password default: {get_default_parent_password()}",
                    "info",
                )
            return redirect(url_for("siswa_list"))
        except Exception as e:
            flash(f"Gagal: {e}", "danger")
    return render_template(
        "siswa_form.html", item=None, kelas=kelas, musyrif=musyrif, nama_orang_tua=""
    )


@app.route("/siswa/<int:sid>/edit", methods=["GET", "POST"])
@admin_required
def siswa_edit(sid):
    ta = current_ta_id()
    item = query_one(
        """
        SELECT s.*, u.username AS nama_orang_tua
        FROM siswa s
        LEFT JOIN users u ON u.id = s.orang_tua_user_id
        WHERE s.id=%s
        """,
        (sid,),
    )
    kelas = query_all(
        "SELECT * FROM kelas WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY jenjang, nama",
        (ta["id"],),
    )
    musyrif = query_all(
        "SELECT * FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY nama",
        (ta["id"],),
    )
    if not item:
        flash("Siswa tidak ditemukan.", "danger")
        return redirect(url_for("siswa_list"))
    if request.method == "POST":
        try:
            ortu_id = ensure_parent_account(
                request.form.get("nama_orang_tua", ""),
                request.form.get("telepon_orang_tua") or None,
            )
            execute(
                "UPDATE siswa SET nis=%s, nama=%s, jenis_kelamin=%s, kelas_id=%s, "
                "musyrif_id=%s, orang_tua_user_id=%s, aktif=%s WHERE id=%s",
                (
                    request.form.get("nis", "").strip(),
                    request.form.get("nama", "").strip(),
                    request.form.get("jenis_kelamin", "L"),
                    request.form.get("kelas_id"),
                    request.form.get("musyrif_id") or None,
                    ortu_id,
                    1 if request.form.get("aktif") == "1" else 0,
                    sid,
                ),
            )
            flash("Data siswa diperbarui.", "success")
            return redirect(url_for("siswa_list"))
        except Exception as e:
            flash(f"Gagal: {e}", "danger")
    return render_template(
        "siswa_form.html",
        item=item,
        kelas=kelas,
        musyrif=musyrif,
        nama_orang_tua=item.get("nama_orang_tua") or "",
    )


@app.route("/siswa/<int:sid>/hapus", methods=["POST"])
@admin_required
def siswa_hapus(sid):
    execute("DELETE FROM siswa WHERE id=%s", (sid,))
    flash("Siswa dihapus.", "info")
    return redirect(url_for("siswa_list"))


# ─── Setoran (Realtime Logging) ───────────────────────────────
@app.route("/setoran", methods=["GET", "POST"])
@staff_required
def setoran():
    ta = current_ta_id()
    if not ta:
        return redirect(url_for("tahun_ajaran"))

    siswa = query_all(
        """
        SELECT s.id, s.nis, s.nama, k.nama AS nama_kelas
        FROM siswa s JOIN kelas k ON k.id = s.kelas_id
        WHERE s.tahun_ajaran_id=%s AND s.aktif=1
        ORDER BY k.jenjang, k.nama, s.nama
        """,
        (ta["id"],),
    )
    musyrif = query_all(
        "SELECT * FROM musyrif WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY nama",
        (ta["id"],),
    )

    if request.method == "POST":
        nilai = int(request.form.get("nilai", 0) or 0)
        predikat = f"{predikat_huruf(nilai)} ({nilai}) - {predikat_dari_nilai(nilai)}"
        tanggal_str = request.form.get("tanggal") or datetime.now().strftime("%Y-%m-%dT%H:%M")
        try:
            tanggal = datetime.strptime(tanggal_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            tanggal = datetime.now()
        try:
            execute(
                """
                INSERT INTO setoran
                  (siswa_id, tahun_ajaran_id, tanggal, jenis, surah, ayat_awal, ayat_akhir,
                   juz, volume_halaman, volume_baris, nilai, predikat, status, catatan, musyrif_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    request.form.get("siswa_id"),
                    ta["id"],
                    tanggal,
                    request.form.get("jenis"),
                    request.form.get("surah", "").strip(),
                    request.form.get("ayat_awal") or None,
                    request.form.get("ayat_akhir") or None,
                    request.form.get("juz") or None,
                    float(request.form.get("volume_halaman") or 0),
                    float(request.form.get("volume_baris") or 0),
                    nilai,
                    predikat,
                    request.form.get("status", "Lulus"),
                    request.form.get("catatan", "").strip() or None,
                    request.form.get("musyrif_id") or None,
                ),
            )
            # update evaluasi otomatis dari rata-rata nilai lulus
            _sync_evaluasi(int(request.form.get("siswa_id")), ta["id"])
            flash("Setoran berhasil dicatat (realtime).", "success")
            return redirect(url_for("setoran"))
        except Exception as e:
            flash(f"Gagal menyimpan setoran: {e}", "danger")

    log = query_all(
        """
        SELECT st.*, s.nama AS nama_siswa, k.nama AS nama_kelas, m.nama AS nama_musyrif
        FROM setoran st
        JOIN siswa s ON s.id = st.siswa_id
        JOIN kelas k ON k.id = s.kelas_id
        LEFT JOIN musyrif m ON m.id = st.musyrif_id
        WHERE st.tahun_ajaran_id=%s
        ORDER BY st.tanggal DESC
        LIMIT 50
        """,
        (ta["id"],),
    )
    return render_template(
        "setoran.html",
        siswa=siswa,
        musyrif=musyrif,
        log=log,
        now=datetime.now().strftime("%Y-%m-%dT%H:%M"),
    )


@app.route("/setoran/<int:stid>/hapus", methods=["POST"])
@staff_required
def setoran_hapus(stid):
    row = query_one("SELECT * FROM setoran WHERE id=%s", (stid,))
    if row:
        execute("DELETE FROM setoran WHERE id=%s", (stid,))
        _sync_evaluasi(row["siswa_id"], row["tahun_ajaran_id"])
        flash("Setoran dihapus.", "info")
    return redirect(url_for("setoran"))


def _sync_evaluasi(siswa_id, ta_id):
    """Sinkron evaluasi kualitas dari rata-rata nilai setoran Lulus."""
    avg = query_one(
        """
        SELECT AVG(nilai) AS avg_nilai FROM setoran
        WHERE siswa_id=%s AND tahun_ajaran_id=%s AND status='Lulus'
        """,
        (siswa_id, ta_id),
    )
    base = int(round(avg["avg_nilai"] or 0))
    # Default distribusi: kelancaran = base, tajwid/makharijul sedikit di bawah, adab tetap tinggi jika ada data
    if base == 0:
        return
    kelancaran = base
    tajwid = max(0, base - 2)
    makharijul = max(0, base - 5)
    adab = min(100, base + 3)
    existing = query_one(
        "SELECT id FROM evaluasi WHERE siswa_id=%s AND tahun_ajaran_id=%s",
        (siswa_id, ta_id),
    )
    if existing:
        execute(
            "UPDATE evaluasi SET kelancaran=%s, tajwid=%s, makharijul=%s, adab=%s "
            "WHERE siswa_id=%s AND tahun_ajaran_id=%s",
            (kelancaran, tajwid, makharijul, adab, siswa_id, ta_id),
        )
    else:
        execute(
            "INSERT INTO evaluasi (siswa_id, tahun_ajaran_id, kelancaran, tajwid, makharijul, adab) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (siswa_id, ta_id, kelancaran, tajwid, makharijul, adab),
        )


# ─── Laporan Murid (Realtime) ─────────────────────────────────
@app.route("/laporan")
@login_required
def laporan_index():
    ta = current_ta_id()
    if not ta:
        return redirect(url_for("tahun_ajaran"))
    q = request.args.get("q", "").strip()
    kelas_id = request.args.get("kelas_id", "")
    sql = """
        SELECT s.id, s.nis, s.nama, k.nama AS nama_kelas, k.jenjang, m.nama AS nama_musyrif,
               COALESCE(SUM(CASE WHEN st.status='Lulus' AND st.jenis='Ziyadah'
                                 THEN st.volume_halaman ELSE 0 END), 0) AS total_halaman
        FROM siswa s
        JOIN kelas k ON k.id = s.kelas_id
        LEFT JOIN musyrif m ON m.id = COALESCE(s.musyrif_id, k.musyrif_id)
        LEFT JOIN setoran st ON st.siswa_id = s.id AND st.tahun_ajaran_id = s.tahun_ajaran_id
        WHERE s.tahun_ajaran_id=%s AND s.aktif=1
    """
    params = [ta["id"]]
    # Orang tua hanya melihat anaknya
    if is_parent():
        sql += " AND s.orang_tua_user_id=%s"
        params.append(session["user_id"])
    if q:
        sql += " AND (s.nama LIKE %s OR s.nis LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if kelas_id and not is_parent():
        sql += " AND s.kelas_id=%s"
        params.append(kelas_id)
    sql += " GROUP BY s.id ORDER BY k.jenjang, k.nama, s.nama"
    daftar = query_all(sql, params)
    for row in daftar:
        row["progress"] = hitung_progress(row["total_halaman"], row["jenjang"], ta["semester"])
    kelas = []
    if not is_parent():
        kelas = query_all(
            "SELECT * FROM kelas WHERE tahun_ajaran_id=%s AND aktif=1 ORDER BY jenjang, nama",
            (ta["id"],),
        )
    return render_template(
        "laporan_index.html", daftar=daftar, kelas=kelas, q=q, kelas_id=kelas_id
    )


@app.route("/laporan/<int:sid>")
@login_required
def laporan_detail(sid):
    ta = current_ta_id()
    if is_parent() and not parent_owns_siswa(session["user_id"], sid):
        flash("Anda tidak berhak melihat laporan murid ini.", "danger")
        return redirect(url_for("dashboard"))
    siswa = query_one(
        """
        SELECT s.*, k.nama AS nama_kelas, k.jenjang,
               m.nama AS nama_musyrif, m.gelar AS gelar_musyrif
        FROM siswa s
        JOIN kelas k ON k.id = s.kelas_id
        LEFT JOIN musyrif m ON m.id = COALESCE(s.musyrif_id, k.musyrif_id)
        WHERE s.id=%s
        """,
        (sid,),
    )
    if not siswa:
        flash("Siswa tidak ditemukan.", "danger")
        return redirect(url_for("laporan_index"))

    total = query_one(
        """
        SELECT COALESCE(SUM(CASE WHEN status='Lulus' AND jenis='Ziyadah'
                                 THEN volume_halaman ELSE 0 END), 0) AS total_halaman
        FROM setoran WHERE siswa_id=%s AND tahun_ajaran_id=%s
        """,
        (sid, ta["id"]),
    )
    progress = hitung_progress(total["total_halaman"], siswa["jenjang"], ta["semester"])

    log = query_all(
        """
        SELECT st.*, m.nama AS nama_musyrif
        FROM setoran st
        LEFT JOIN musyrif m ON m.id = st.musyrif_id
        WHERE st.siswa_id=%s AND st.tahun_ajaran_id=%s
        ORDER BY st.tanggal DESC
        """,
        (sid, ta["id"]),
    )

    evaluasi = query_one(
        "SELECT * FROM evaluasi WHERE siswa_id=%s AND tahun_ajaran_id=%s",
        (sid, ta["id"]),
    )
    if not evaluasi:
        evaluasi = {"kelancaran": 0, "tajwid": 0, "makharijul": 0, "adab": 0}

    evaluasi_rows = [
        ("Kelancaran Hafalan (Fashohah / Mutqin)", evaluasi["kelancaran"]),
        ("Ketepatan Hukum Tajwid & Panjang Pendek (Mad)", evaluasi["tajwid"]),
        ("Makharijul Huruf & Sifat Huruf", evaluasi["makharijul"]),
        ("Adab, Kehadiran, & Kedisiplinan Halaqah", evaluasi["adab"]),
    ]
    evaluasi_display = [
        {
            "no": i + 1,
            "elemen": nama,
            "nilai": nilai,
            "predikat": predikat_dari_nilai(nilai),
        }
        for i, (nama, nilai) in enumerate(evaluasi_rows)
    ]

    # Target skema lengkap
    targets = []
    for (jenjang, sem), meta in TARGET_MAP.items():
        targets.append(
            {
                "tingkat": f"Kelas {jenjang} SMP",
                "periode": f"Semester {sem}",
                "ziyadah": meta["ziyadah"],
                "kumulatif": meta["kumulatif"],
                "aktif": jenjang == siswa["jenjang"] and int(ta["semester"]) == sem,
            }
        )

    return render_template(
        "laporan_detail.html",
        siswa=siswa,
        progress=progress,
        log=log,
        evaluasi=evaluasi_display,
        targets=targets,
        ta=ta,
    )


@app.route("/laporan/<int:sid>/evaluasi", methods=["POST"])
@staff_required
def evaluasi_update(sid):
    ta = current_ta_id()
    vals = (
        int(request.form.get("kelancaran") or 0),
        int(request.form.get("tajwid") or 0),
        int(request.form.get("makharijul") or 0),
        int(request.form.get("adab") or 0),
        sid,
        ta["id"],
    )
    existing = query_one(
        "SELECT id FROM evaluasi WHERE siswa_id=%s AND tahun_ajaran_id=%s",
        (sid, ta["id"]),
    )
    if existing:
        execute(
            "UPDATE evaluasi SET kelancaran=%s, tajwid=%s, makharijul=%s, adab=%s "
            "WHERE siswa_id=%s AND tahun_ajaran_id=%s",
            vals,
        )
    else:
        execute(
            "INSERT INTO evaluasi (kelancaran, tajwid, makharijul, adab, siswa_id, tahun_ajaran_id) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            vals,
        )
    flash("Evaluasi kualitas diperbarui.", "success")
    return redirect(url_for("laporan_detail", sid=sid))


# ─── Blanko Unduh & Upload (satu file gabungan) ───────────────
@app.route("/blanko")
@staff_required
def blanko_page():
    return render_template("blanko.html")


@app.route("/blanko/unduh")
@app.route("/blanko/unduh/<jenis>")
@staff_required
def blanko_unduh(jenis=None):
    """Unduh blanko gabungan (satu tabel: musyrif + kelas + siswa)."""
    try:
        bio = generate_blanko_combined()
        return send_file(
            bio,
            as_attachment=True,
            download_name="blanko_data_tahfidz.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        flash(f"Gagal membuat blanko: {e}", "danger")
        return redirect(url_for("blanko_page"))


@app.route("/blanko/upload", methods=["POST"])
@app.route("/blanko/upload/<jenis>", methods=["POST"])
@admin_required
def blanko_upload(jenis=None):
    """Upload blanko gabungan — otomatis upsert musyrif, kelas, siswa."""
    ta = current_ta_id()
    if not ta:
        flash("Pilih tahun ajaran terlebih dahulu.", "warning")
        return redirect(url_for("blanko_page"))

    f = request.files.get("file")
    if not f or not f.filename:
        flash("Pilih file Excel terlebih dahulu.", "danger")
        return redirect(url_for("blanko_page"))

    try:
        rows = parse_blanko_combined(f)
    except Exception as e:
        flash(f"File tidak valid: {e}", "danger")
        return redirect(url_for("blanko_page"))

    if not rows:
        flash("Tidak ada baris data di file.", "warning")
        return redirect(url_for("blanko_page"))

    ok_m, ok_k, ok_s = 0, 0, 0
    fail = 0
    errors = []
    seen_musyrif = set()
    seen_kelas = set()

    for r in rows:
        try:
            kode_m = (r.get("kode_musyrif") or "").strip()
            nama_m = (r.get("nama_musyrif") or "").strip()
            musyrif_id = None

            if kode_m and nama_m and kode_m not in seen_musyrif:
                execute(
                    "INSERT INTO musyrif (kode, nama, gelar, telepon, tahun_ajaran_id) "
                    "VALUES (%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE nama=VALUES(nama), gelar=VALUES(gelar), "
                    "telepon=VALUES(telepon), aktif=1",
                    (
                        kode_m,
                        nama_m,
                        r.get("gelar_musyrif") or None,
                        r.get("telepon_musyrif") or None,
                        ta["id"],
                    ),
                )
                seen_musyrif.add(kode_m)
                ok_m += 1
            elif kode_m and not nama_m:
                # sudah ada di DB, cukup lookup
                pass

            if kode_m:
                m = query_one(
                    "SELECT id FROM musyrif WHERE kode=%s AND tahun_ajaran_id=%s",
                    (kode_m, ta["id"]),
                )
                if m:
                    musyrif_id = m["id"]

            nama_kelas = (r.get("nama_kelas") or "").strip()
            jenjang_raw = (r.get("jenjang") or "").strip()
            if nama_kelas and jenjang_raw:
                jenjang = int(float(jenjang_raw))
                key_k = nama_kelas.lower()
                if key_k not in seen_kelas:
                    execute(
                        "INSERT INTO kelas (nama, jenjang, tahun_ajaran_id, musyrif_id) "
                        "VALUES (%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE jenjang=VALUES(jenjang), "
                        "musyrif_id=COALESCE(VALUES(musyrif_id), musyrif_id), aktif=1",
                        (nama_kelas, jenjang, ta["id"], musyrif_id),
                    )
                    seen_kelas.add(key_k)
                    ok_k += 1

            nis = (r.get("nis") or "").strip()
            nama_siswa = (r.get("nama_siswa") or "").strip()
            if not nis or not nama_siswa:
                continue
            if not nama_kelas:
                raise ValueError("nama_kelas wajib untuk baris siswa")

            kelas = query_one(
                "SELECT id FROM kelas WHERE nama=%s AND tahun_ajaran_id=%s",
                (nama_kelas, ta["id"]),
            )
            if not kelas:
                raise ValueError(f"Kelas '{nama_kelas}' gagal dibuat/ditemukan")

            jk = (r.get("jenis_kelamin") or "L").upper()[:1]
            if jk not in ("L", "P"):
                jk = "L"
            ortu_id = ensure_parent_account(
                r.get("nama_orang_tua", ""),
                r.get("telepon_orang_tua") or None,
            )
            execute(
                "INSERT INTO siswa (nis, nama, jenis_kelamin, kelas_id, musyrif_id, "
                "orang_tua_user_id, tahun_ajaran_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE nama=VALUES(nama), jenis_kelamin=VALUES(jenis_kelamin), "
                "kelas_id=VALUES(kelas_id), musyrif_id=VALUES(musyrif_id), "
                "orang_tua_user_id=COALESCE(VALUES(orang_tua_user_id), orang_tua_user_id), aktif=1",
                (nis, nama_siswa, jk, kelas["id"], musyrif_id, ortu_id, ta["id"]),
            )
            ok_s += 1
        except Exception as e:
            fail += 1
            label = r.get("nis") or r.get("kode_musyrif") or r.get("nama_kelas") or "?"
            errors.append(f"{label}: {e}")

    msg = f"Import gabungan: {ok_m} musyrif, {ok_k} kelas, {ok_s} siswa"
    if fail:
        msg += f" · {fail} baris gagal"
        if errors:
            msg += " — " + "; ".join(errors[:5])
    flash(msg, "success" if fail == 0 else "warning")
    return redirect(url_for("blanko_page"))


# ─── Kelola Orang Tua (admin) ─────────────────────────────────
@app.route("/orang-tua")
@admin_required
def orang_tua_list():
    daftar = query_all(
        """
        SELECT u.id, u.username, u.nama_lengkap, u.aktif, u.must_change_password, u.created_at,
               (SELECT COUNT(*) FROM siswa s WHERE s.orang_tua_user_id=u.id AND s.aktif=1) AS jml_anak
        FROM users u
        WHERE u.role='orang_tua'
        ORDER BY u.username
        """
    )
    return render_template(
        "orang_tua.html",
        daftar=daftar,
        default_password=get_default_parent_password(),
    )


@app.route("/orang-tua/password-default", methods=["POST"])
@admin_required
def orang_tua_set_default_password():
    baru = request.form.get("password_default", "").strip()
    try:
        set_default_parent_password(baru)
        flash(f"Password default orang tua diubah menjadi: {baru}", "success")
    except Exception as e:
        flash(f"Gagal: {e}", "danger")
    return redirect(url_for("orang_tua_list"))


@app.route("/orang-tua/<int:uid>/reset", methods=["POST"])
@admin_required
def orang_tua_reset(uid):
    custom = request.form.get("password_custom", "").strip() or None
    user = query_one("SELECT * FROM users WHERE id=%s AND role='orang_tua'", (uid,))
    if not user:
        flash("Akun orang tua tidak ditemukan.", "danger")
        return redirect(url_for("orang_tua_list"))
    reset_parent_password(uid, custom)
    pw = custom or get_default_parent_password()
    flash(
        f"Password '{user['username']}' direset ke: {pw}. Orang tua diminta mengganti saat login.",
        "success",
    )
    return redirect(url_for("orang_tua_list"))


@app.route("/orang-tua/reset-semua", methods=["POST"])
@admin_required
def orang_tua_reset_semua():
    reset_all_parent_passwords_to_default()
    flash(
        f"Semua password orang tua direset ke default: {get_default_parent_password()}",
        "success",
    )
    return redirect(url_for("orang_tua_list"))


@app.route("/orang-tua/<int:uid>/toggle", methods=["POST"])
@admin_required
def orang_tua_toggle(uid):
    user = query_one("SELECT * FROM users WHERE id=%s AND role='orang_tua'", (uid,))
    if user:
        execute(
            "UPDATE users SET aktif=%s WHERE id=%s",
            (0 if user["aktif"] else 1, uid),
        )
        flash("Status akun diperbarui.", "info")
    return redirect(url_for("orang_tua_list"))


# ─── Users (admin) ────────────────────────────────────────────
@app.route("/users", methods=["GET", "POST"])
@admin_required
def users_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        nama = request.form.get("nama_lengkap", "").strip()
        role = request.form.get("role", "musyrif")
        password = request.form.get("password", "")
        if role == "orang_tua":
            flash("Akun orang tua dibuat lewat data siswa / menu Orang Tua.", "warning")
            return redirect(url_for("users_page"))
        if not username or not password or not nama:
            flash("Semua field wajib diisi.", "danger")
        else:
            try:
                execute(
                    "INSERT INTO users (username, password_hash, nama_lengkap, role) VALUES (%s,%s,%s,%s)",
                    (username, generate_password_hash(password), nama, role),
                )
                flash("User ditambahkan.", "success")
            except Exception as e:
                flash(f"Gagal: {e}", "danger")
        return redirect(url_for("users_page"))
    daftar = query_all(
        "SELECT id, username, nama_lengkap, role, aktif, created_at FROM users "
        "WHERE role IN ('admin','musyrif') ORDER BY id"
    )
    return render_template("users.html", daftar=daftar)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)