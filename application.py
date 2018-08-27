import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # query database for number of stocks in portfolio
    transactions = db.execute("SELECT stockname, stocksymbol, sum(shares) FROM transactions WHERE userID = :userID GROUP BY stocksymbol ORDER BY stocksymbol",
                              userID=session["user_id"])

    # query database for cash in user account
    cash = db.execute("SELECT cash FROM users WHERE id = :userID",
                      userID=session["user_id"])

    totalValue = cash[0]["cash"]

    # iterate over stocks in the portfolio
    for transaction in transactions:

        # lookup current prices of stocks
        price = lookup(transaction["stocksymbol"])["price"]

        # add price as new key and add current price as value
        transaction["price"] = price

        # add total price as new key and add total value as value
        transaction["total"] = transaction["price"] * transaction["sum(shares)"]

        totalValue += transaction["total"]

        # format values in USD
        transaction["price"] = usd(transaction["price"])
        transaction["total"] = usd(transaction["total"])

    return render_template("index.html", transactions=transactions, cash=usd(cash[0]["cash"]), totalValue=usd(totalValue))


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    """Buy shares of stock"""
    if request.method == "POST":

        additionalCash = request.form.get("cash")

        # redundant since buy.html specifies this requirement, but required as per C$50 Finance specs I guess
        if int(additionalCash) <= 0:
            return apology("must use positive number", 400)

        else:
            # subtracts amount from cash
            db.execute("UPDATE users SET cash = cash + :additionalCash WHERE id = :userid",
                       additionalCash=int(additionalCash),
                       userid=session["user_id"])

        # redirect user to main page
        return redirect("/")

    # user reached route via GET (redirect or link)
    else:
        return render_template("addcash.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        symbol = request.form.get("symbol")
        numShares = request.form.get("shares")
        quote = lookup(symbol)

        # ensure symbol is inputted
        if not symbol:
            return apology("must provide symbol", 400)

        # ensures numeric input
        elif not symbol.isalpha() or not numShares.isdigit():
            return apology("invalid input", 400)

        # ensure symbol is valid
        elif not quote:
            return apology("invalid symbol", 400)

        # redundant since buy.html specifies this requirement, but required as per C$50 Finance specs I guess
        elif not numShares or float(numShares) < 0 or not float(numShares).is_integer():
            return apology("must use positive whole number", 400)

        # query database for user
        rows = db.execute("SELECT * FROM users WHERE id = :userid",
                          userid=session["user_id"])

        totalPrice = int(numShares) * quote["price"]

        # checks for insufficient funds
        if rows[0]["cash"] < totalPrice:
            return apology("insufficient funds", 400)

        else:
            # subtracts amount from cash
            db.execute("UPDATE users SET cash = cash - :totalPrice WHERE id = :userid",
                       totalPrice=totalPrice,
                       userid=session["user_id"])

           # adds new stock to portfolio
            db.execute("INSERT INTO transactions (transactionID, stocksymbol, stockname, shares, price, total, userID) VALUES (NULL, :stocksymbol, :stockname, :shares, :price, :total, :userID)",
                       stocksymbol=quote["symbol"],
                       stockname=quote["name"],
                       shares=numShares,
                       price=quote["price"],
                       total=totalPrice,
                       userID=session["user_id"])

        # redirect user to main page
        return redirect("/")

    # user reached route via GET (redirect or link)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # query database for number of stocks in portfolio
    transactions = db.execute("SELECT stocksymbol, shares, price, timestamp FROM transactions WHERE userID = :userID ORDER BY timestamp",
                              userID=session["user_id"])

    # iterate over stocks in the portfolio
    for transaction in transactions:

        # format values in USD
        transaction["price"] = usd(transaction["price"])

    return render_template("history.html", transactions=transactions)


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
    if request.method == "POST":

        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        # ensure symbol is inputted
        if not symbol:
            return apology("must provide symbol", 400)

        # ensure symbol is valid
        elif not quote:
            return apology("invalid symbol", 400)

        quote["price"] = usd(quote["price"])

        # redirect user to main page
        return render_template("quoted.html", quote=quote)

    # user reached route via GET (redirect or link)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # ensure username is inputted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # ensure password is inputted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # ensures the two passwords match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # query database for existing username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # ensure username does not already exist
        if len(rows) == 1:
            return apology("username already exists", 400)

        # creates a new user
        newUser = db.execute("INSERT INTO users (id, username, hash, cash) VALUES (NULL, :username, :hashfunction, 10000)",
                             username=request.form.get("username"),
                             hashfunction=generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8))

        # remembers which user has logged in
        session["user_id"] = newUser

        # redirect user to main page
        return redirect("/")

    # user reached route via GET (redirect or link)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        numShares = request.form.get("shares")
        quote = lookup(symbol)

        # ensure symbol is inputted
        if not symbol:
            return apology("must provide symbol", 400)

        # ensure symbol is valid
        elif not quote:
            return apology("invalid symbol", 400)

        # redundant since buy.html specifies this requirement, but required as per C$50 Finance specs I guess
        elif not numShares:
            return apology("must use positive number", 400)

        # calculates how many shares are owned of the specified stock
        transactions = db.execute("SELECT stockname, stocksymbol, sum(shares) FROM transactions WHERE userID = :userID AND stocksymbol = :stocksymbol GROUP BY stocksymbol ORDER BY stocksymbol",
                                  userID=session["user_id"],
                                  stocksymbol=quote["symbol"])

        # if attempting to sell a stock not in portfolio or selling more stock than is in portfolio
        if len(transactions) == 0 or int(numShares) > transactions[0]["sum(shares)"]:
            return apology("not enough stock owned to sell", 400)

        totalPrice = int(numShares) * quote["price"]

        # adds transaction details to transaction table
        db.execute("INSERT INTO transactions (transactionID, stocksymbol, stockname, shares, price, total, userID) VALUES (NULL, :stocksymbol, :stockname, :shares, :price, :total, :userID)",
                   stocksymbol=quote["symbol"],
                   stockname=quote["name"],
                   shares=-int(numShares),
                   price=quote["price"],
                   total=totalPrice,
                   userID=session["user_id"])

        # adds cash balance to users table
        db.execute("UPDATE users SET cash = cash + :totalPrice WHERE id = :userid",
                   totalPrice=totalPrice,
                   userid=session["user_id"])

        return redirect("/")

    else:
        # query database for number of stocks in portfolio
        ownedStocks = db.execute("SELECT stocksymbol FROM transactions WHERE userID = :userID GROUP BY stocksymbol ORDER BY stocksymbol",
                                 userID=session["user_id"])

    return render_template("sell.html", ownedStocks=ownedStocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
