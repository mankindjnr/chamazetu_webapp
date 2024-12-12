// notification
    document.addEventListener("DOMContentLoaded", function() {
  var chama_created = document.getElementById("chama_created");
  if (chama_created) {
    setTimeout(function() {
      chama_created.style.display = "none";
    }, 5000);
  }
});

document.addEventListener("DOMContentLoaded", function() {
  var chama_created = document.getElementById("message_created");
  if (chama_created) {
    setTimeout(function() {
      chama_created.style.display = "none";
    }, 5000);
  }
});