import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("""SELECT symbol, SUM(shares) as totalSHARES
        FROM transactions
        WHERE user_id = :user_id
        GROUP BY symbol""",
        user_id=session["user_id"])
    capital = []
    total2 = 0
    for row in rows:
        stock = lookup(row["symbol"])
        capital.append({"symbol": stock["symbol"], "name": stock["name"], "shares": row["totalSHARES"], "price": usd(stock["price"]),
        "total": usd(stock["price"] * row["totalSHARES"])})
        total2 += stock["price"] * row["totalSHARES"]
    rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    cash = usd(rows[0]["cash"])
    total2 += rows[0]["cash"]

    return render_template("index.html", capital=capital, cash=cash, total2=usd(total2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        if not symbol:
            return apology("You must provide a symbol.", 403)
        if not shares:
            return apology("You must provide shares.", 403)
        stock = lookup(symbol)
        if stock is None:
            return apology("Invalid symbol!", 403)
        rows = db.execute("SELECT cash FROM users WHERE id = :id",
                          id=session["user_id"])
        user_cash = rows[0]["cash"]
        updated_cash = user_cash - shares * stock["price"]
        if updated_cash < 0:
            return apology("You don't have enough cash.", 403)
        db.execute("UPDATE users SET cash=:updated_cash WHERE id=:id", updated_cash=updated_cash, id=session["user_id"])
        db.execute("""INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)""",
            user_id = session["user_id"],
            symbol = stock["symbol"],
            shares = shares,
            price = stock["price"])
        flash("Success! You bought it!")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("""SELECT symbol, shares, price, time
        FROM transactions
        WHERE user_id = :user_id""",
        user_id=session["user_id"])
    capital = []
    for row in rows:
        capital.append({"symbol": row["symbol"], "shares": row["shares"], "price": row["price"], "time": row["time"]})
    return render_template("history.html", capital=capital)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("You must provide a symbol.", 403)
        stock = lookup(symbol)
        if stock is None:
            return apology("Invalid symbol!", 403)
        return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=usd(stock["price"]))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if len(password) < 6:
            return apology("Your password must contains min 6 characters", 403)

        elif password != confirmation:
            return apology("Passwords do not match.", 403)

        elif not username:
            return apology("You must provide a username.", 403)

        elif not password:
            return apology("You must provide a password.", 403)

        elif not confirmation:
            return apology("You must provide a password confirmation.", 403)

        password_hash = generate_password_hash(password)
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=password_hash)
        except:
            return apology("The username already exist", 403)
        return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        symbols = []
        shares = []
        rows = db.execute("""SELECT symbol, SUM(shares) as totalSHARES
        FROM transactions
        WHERE user_id = :user_id
        GROUP BY symbol""",
        user_id=session["user_id"])
        for row in rows:
            symbols.append(row["symbol"])
            symbols.append(row["totalSHARES"])
        return render_template("sell.html", symbols=symbols, shares=shares)
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        stock = lookup(symbol)
        if not symbol:
            return apology("You must provide a symbol.", 403)
        if not shares:
            return apology("You must provide shares.", 403)
        rows = db.execute("""SELECT symbol, SUM(shares) as totalSHARES
            FROM transactions
            WHERE user_id = :user_id
            GROUP BY symbol""",
            user_id=session["user_id"])
        for row in rows:
            if row["symbol"] == symbol:
                if shares > row["totalSHARES"]:
                    return apology("You do not own that many shares of the stock", 403)
        rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        cash = rows[0]["cash"]
        updated_cash = cash + shares * stock["price"]
        db.execute("UPDATE users SET cash=:updated_cash WHERE id=:id", updated_cash=updated_cash, id=session["user_id"])
        db.execute("""INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)""",
            user_id = session["user_id"],
            symbol = stock["symbol"],
            shares = shares * -1,
            price = stock["price"])
        flash("Success, you sold it!")
        return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)