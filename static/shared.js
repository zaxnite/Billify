// Shared JavaScript for all pages
document.addEventListener('DOMContentLoaded', function() {
  // Mobile navigation toggle
  const toggleBtn = document.querySelector(".toggle_btn");
  const toggleBtnIcon = document.querySelector(".toggle_btn i");
  const dropDownMenu = document.querySelector(".dropdown_menu");

  if (toggleBtn && dropDownMenu) {
    toggleBtn.onclick = function () {
      dropDownMenu.classList.toggle("open");
      const isOpen = dropDownMenu.classList.contains("open");
      
      if (toggleBtnIcon) {
        toggleBtnIcon.classList = isOpen
          ? "fa-solid fa-xmark"
          : "fa-solid fa-bars";
      }
    };
  }

  // Theme toggle functionality
  const checkbox = document.getElementById('checkbox');
  const body = document.body;
  
  if (checkbox) {
    // Check for saved theme preference or default to light mode
    const currentTheme = localStorage.getItem('theme') || 'light';
    
    if (currentTheme === 'dark') {
      body.classList.add('dark-mode');
      checkbox.checked = true;
    }
    
    // Listen for toggle changes
    checkbox.addEventListener('change', function() {
      if (this.checked) {
        body.classList.add('dark-mode');
        localStorage.setItem('theme', 'dark');
      } else {
        body.classList.remove('dark-mode');
        localStorage.setItem('theme', 'light');
      }
    });
  }
});
