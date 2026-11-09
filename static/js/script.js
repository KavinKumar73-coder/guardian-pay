/* ==================================================
   Guardian Pay - client-side enhancements
   Place at: static/js/script.js

   Everything here is progressive enhancement. The
   app works without JavaScript, and all security
   checks (CSRF, amount, guardian token) stay on
   the server.
   ================================================== */

(function () {
    "use strict";

    // ---------- Message character counter ----------
    var message = document.getElementById("message");
    var counter = document.getElementById("message-count");

    if (message && counter) {
        var max = parseInt(counter.dataset.max, 10) || 1000;

        var updateCounter = function () {
            var length = message.value.length;
            counter.textContent = length + " / " + max;
            counter.classList.toggle("is-near-limit", length >= max * 0.9);
        };

        message.addEventListener("input", updateCounter);
        updateCounter();
    }

    // ---------- Friendlier amount validation messages ----------
    var amount = document.getElementById("amount");

    if (amount) {
        amount.addEventListener("input", function () {
            amount.setCustomValidity("");
        });

        amount.addEventListener("invalid", function () {
            var v = amount.validity;

            if (v.stepMismatch) {
                amount.setCustomValidity(
                    "Use up to two decimal places, like 25.50."
                );
            } else if (v.rangeUnderflow || v.rangeOverflow) {
                amount.setCustomValidity(
                    "Enter an amount between $0.01 and $100,000."
                );
            }
        });
    }

    // ---------- Prevent double submission ----------
    // Buttons are NOT disabled: a disabled submit button is left out
    // of the form data, which would drop the guardian's
    // action=approve / action=deny value.
    var forms = document.querySelectorAll("form[data-submit-once]");

    forms.forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (form.dataset.submitting === "true") {
                event.preventDefault();
                return;
            }

            form.dataset.submitting = "true";
            form.classList.add("is-busy");

            var button =
                event.submitter ||
                form.querySelector("button[type='submit'], button:not([type])");

            if (button && button.dataset.busyLabel) {
                button.dataset.originalLabel = button.textContent;
                button.textContent = button.dataset.busyLabel;
            }
        });
    });

    // Restore forms if the browser shows this page from its
    // back/forward cache (e.g. after returning from PayPal).
    window.addEventListener("pageshow", function (event) {
        if (!event.persisted) {
            return;
        }

        forms.forEach(function (form) {
            form.dataset.submitting = "false";
            form.classList.remove("is-busy");

            form.querySelectorAll("button").forEach(function (button) {
                if (button.dataset.originalLabel) {
                    button.textContent = button.dataset.originalLabel;
                }
            });
        });
    });

    // ---------- Copy guardian link ----------
    document.querySelectorAll("[data-copy-target]").forEach(function (button) {
        button.addEventListener("click", function () {
            var source = document.querySelector(button.dataset.copyTarget);

            if (!source) {
                return;
            }

            var original = button.textContent;

            var done = function (text) {
                button.textContent = text;
                window.setTimeout(function () {
                    button.textContent = original;
                }, 2000);
            };

            var fallback = function () {
                source.focus();
                source.select();

                try {
                    done(document.execCommand("copy") ? "Copied" : "Press Ctrl+C");
                } catch (error) {
                    done("Press Ctrl+C");
                }
            };

            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(source.value).then(
                    function () { done("Copied"); },
                    fallback
                );
            } else {
                fallback();
            }
        });
    });
})();
