document.addEventListener('DOMContentLoaded', function() {
    const fields = [
        { id: 'seo_title', max: 60 },
        { id: 'seo_description', max: 160 }
    ];

    function setupCounter(input) {
        if (!input || input.nextElementSibling?.classList.contains('char-counter')) return;

        const max = input.getAttribute('data-max') || (input.id.includes('title') ? 60 : 160);
        const counter = document.createElement('div');
        counter.classList.add('char-counter');
        counter.style.fontSize = '12px';
        counter.style.color = '#666';
        counter.style.marginTop = '2px';
        
        function updateCounter() {
            const length = input.value.length;
            counter.textContent = `${length}/${max}`;
            if (length > max) {
                counter.style.color = '#ba2121'; // Django error color
            } else {
                counter.style.color = '#666';
            }
        }

        input.addEventListener('input', updateCounter);
        input.parentNode.insertBefore(counter, input.nextSibling);
        updateCounter();
    }

    // Initial setup for existing fields
    function init() {
        // Direct fields
        fields.forEach(f => {
            const input = document.getElementById('id_' + f.id);
            if (input) {
                input.setAttribute('data-max', f.max);
                setupCounter(input);
            }
        });

        // Inline fields (article-0-seo_title, etc.)
        const inputs = document.querySelectorAll('[id$="seo_title"], [id$="seo_description"]');
        inputs.forEach(input => {
            if (input.id.startsWith('id_article-')) {
                const max = input.id.includes('title') ? 60 : 160;
                input.setAttribute('data-max', max);
                setupCounter(input);
            }
        });
    }

    init();

    // Handle dynamically added inlines if any (though max_num=1 for article)
});
