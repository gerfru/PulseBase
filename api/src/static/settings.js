document.getElementById('profile-save').addEventListener('click', async () => {
    const dob = document.getElementById('dob').value;
    const sex = document.getElementById('sex').value;
    await fetch('/api/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date_of_birth: dob || null, sex: sex || null }),
    });
    const msg = document.getElementById('profile-msg');
    msg.style.display = 'inline';
    setTimeout(() => {
        msg.style.display = 'none';
    }, 3000);
});

document.getElementById('epilepsy-toggle')?.addEventListener('change', async (e) => {
    await fetch('/api/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ epilepsy_mode: e.target.checked }),
    });
    document.getElementById('epilepsy-link').style.display = e.target.checked ? '' : 'none';
});

document.getElementById('spo2-toggle')?.addEventListener('change', async (e) => {
    await fetch('/api/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spo2_enabled: e.target.checked }),
    });
});
