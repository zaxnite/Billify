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

  // Enhanced flag counter handling with debugging
  const flagCounterImg = document.getElementById('flag-counter-img');
  const flagCounterFallback = document.getElementById('flag-counter-fallback');
  
  if (flagCounterImg) {
    console.log('Flag counter element found, setting up handlers...');
    
    // Set initial styles
    flagCounterImg.style.opacity = '0';
    flagCounterImg.style.transition = 'opacity 0.3s ease';
    
    // Success handler
    flagCounterImg.onload = function() {
      console.log('Flag counter loaded successfully');
      this.style.opacity = '1';
      if (flagCounterFallback) {
        flagCounterFallback.style.display = 'none';
      }
    };
    
    // Error handler
    flagCounterImg.onerror = function() {
      console.log('Flag counter failed to load, showing fallback...');
      this.style.display = 'none';
      if (flagCounterFallback) {
        flagCounterFallback.style.display = 'block';
      }
    };
    
    // Timeout fallback - if image doesn't load within 10 seconds
    setTimeout(function() {
      if (flagCounterImg.style.opacity === '0' || flagCounterImg.style.opacity === '') {
        console.log('Flag counter timeout, showing fallback...');
        flagCounterImg.style.display = 'none';
        if (flagCounterFallback) {
          flagCounterFallback.style.display = 'block';
        }
      }
    }, 10000);
    
    // Alternative URLs to try if the main one fails
    const alternativeUrls = [
      'https://s11.flagcounter.com/count2/HTLF/bg_FFFFFF/txt_000000/border_CCCCCC/columns_2/maxflags_10/viewers_0/labels_1/pageviews_0/flags_0/percent_0/',
      'https://s05.flagcounter.com/count2/HTLF/bg_FFFFFF/txt_000000/border_CCCCCC/columns_2/maxflags_10/viewers_0/labels_1/pageviews_0/flags_0/percent_0/',
      'https://flagcounter.com/count2/HTLF/bg_FFFFFF/txt_000000/border_CCCCCC/columns_2/maxflags_10/viewers_0/labels_1/pageviews_0/flags_0/percent_0/'
    ];
    
    let urlIndex = 0;
    function tryNextUrl() {
      if (urlIndex < alternativeUrls.length) {
        console.log('Trying alternative URL:', alternativeUrls[urlIndex]);
        flagCounterImg.src = alternativeUrls[urlIndex];
        urlIndex++;
      }
    }
    
    // If the main URL fails, try alternatives
    const originalOnerror = flagCounterImg.onerror;
    flagCounterImg.onerror = function() {
      if (urlIndex < alternativeUrls.length) {
        tryNextUrl();
      } else {
        originalOnerror.call(this);
      }
    };
  }
  
  // Mobile scrolling fix
  function fixMobileScrolling() {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isiPhoneSE = window.innerWidth <= 320 && window.innerHeight <= 568;
    
    // Ensure body and html can scroll on mobile
    if (window.innerWidth <= 768 || isIOS) {
      document.documentElement.style.overflow = 'auto';
      document.documentElement.style.overflowX = 'hidden';
      document.documentElement.style.webkitOverflowScrolling = 'touch';
      document.documentElement.style.height = 'auto';
      
      document.body.style.overflow = 'auto';
      document.body.style.overflowX = 'hidden';
      document.body.style.webkitOverflowScrolling = 'touch';
      document.body.style.height = 'auto';
      document.body.style.position = 'relative';
      
      // Special fixes for iPhone SE and very small iOS devices
      if (isiPhoneSE || (isIOS && window.innerWidth <= 375)) {
        document.documentElement.style.minHeight = '100%';
        document.documentElement.style.webkitTransform = 'translateZ(0)';
        document.documentElement.style.transform = 'translateZ(0)';
        
        document.body.style.minHeight = '100vh';
        document.body.style.webkitTransform = 'translate3d(0,0,0)';
        document.body.style.transform = 'translate3d(0,0,0)';
        document.body.style.webkitBackfaceVisibility = 'hidden';
        document.body.style.backfaceVisibility = 'hidden';
        
        // Force reflow
        document.body.offsetHeight;
        
        console.log('iPhone SE/small iOS fixes applied');
      }
      
      console.log('Mobile scrolling fixes applied');
    }
  }
  
  // Apply mobile fixes
  fixMobileScrolling();
  
  // Specific iOS scroll fix
  function iosScrollFix() {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS) {
      // Force scroll area recognition
      document.addEventListener('touchstart', function() {}, { passive: true });
      document.addEventListener('touchmove', function(e) {
        // Allow scrolling
        e.stopPropagation();
      }, { passive: true });
      
      // Fix for iOS viewport height issues
      const updateViewport = () => {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
      };
      
      updateViewport();
      window.addEventListener('resize', updateViewport);
      window.addEventListener('orientationchange', updateViewport);
      
      console.log('iOS scroll fixes applied');
    }
  }
  
  iosScrollFix();
  
  // Reapply on resize
  window.addEventListener('resize', function() {
    fixMobileScrolling();
    iosScrollFix();
  });
  
  // Debug information for troubleshooting
  console.log('Page loaded, checking flag counter visibility...');
  console.log('User Agent:', navigator.userAgent);
  console.log('Location:', window.location.href);
});
