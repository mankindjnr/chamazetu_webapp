function toggleStatus(chamaId) {
    var button = document.getElementById('chamastatus');
    var checkbox = document.getElementById('chamaCheckbox');

    // Toggle button class
    if (button.classList.contains('btn-success')) {
        button.classList.remove('btn-success');
        button.classList.add('btn-danger');
        button.textContent = 'inactive';
        checkbox.checked = false;
    } else {
        button.classList.remove('btn-danger');
        button.classList.add('btn-success');
        button.textContent = 'active';
        checkbox.checked = true;
    }

    // Send AJAX request to Django view
    var xhr = new XMLHttpRequest();
    xhr.open('POST', `{% url 'manager:chama_status' %}`, true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
            console.log('Status updated successfully');
        }
    };
    xhr.send('chama_id=' + encodeURIComponent(chamaId) + '&status=' + encodeURIComponent(button.textContent));
}