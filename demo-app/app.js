const form = document.getElementById("checkout-form");
const statusEl = document.getElementById("status");
const countEl = document.getElementById("order-count");

let orders = 0;

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const name = document.getElementById("name").value;
  const email = document.getElementById("email").value;
  const address = document.getElementById("address").value;

  statusEl.textContent = "Processing...";

  // BUG 1: btoa() throws on emoji / non-Latin1 characters,
  // so the page gets stuck on "Processing..."
  const token = btoa(name + "|" + email);

  // BUG 2: the Pay button is never disabled, so double-clicking
  // creates two orders.
  setTimeout(() => {
    // BUG 3: a quote character in the address causes a fake "server error"
    if (address.includes("'")) {
      statusEl.textContent = "Error 500: SQLSTATE[42000] Syntax error near '" + address + "' in /var/www/shop/checkout.php on line 42";
    }
    orders += 1;
    countEl.textContent = orders;
    statusEl.textContent = "Order confirmed! Ref: " + token.slice(0, 8);
    history.pushState({ done: true }, "", "?email=" + encodeURIComponent(email) + "#confirmed");
  }, 800);
});

// BUG 4: pressing Back after payment shows a broken page
window.addEventListener("popstate", () => {
  document.querySelector("main").innerHTML = "<h1>undefined</h1><p>NaN items</p>";
});