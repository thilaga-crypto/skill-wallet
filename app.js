const form = document.getElementById("workoutForm");
const button = document.getElementById("generateBtn");

if (form && button) {
    form.addEventListener("submit", () => {
        button.disabled = true;
        button.textContent = "Generating your plan...";
    });
}
