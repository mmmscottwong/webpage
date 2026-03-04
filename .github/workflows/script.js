gsap.registerPlugin(ScrollTrigger);

const video = document.getElementById('hero-video');
const scrollHint = document.getElementById('scroll-hint');

// ─── NAV background on scroll ──────────────────────────────────────
window.addEventListener('scroll', () => {
  document.getElementById('nav').classList.toggle('nav-solid', window.scrollY > 60);
}, { passive: true });

// ─── Hide scroll hint after first scroll ───────────────────────────
window.addEventListener('scroll', () => {
  if (window.scrollY > 80 && scrollHint) {
    scrollHint.style.opacity = '0';
    scrollHint.style.pointerEvents = 'none';
  }
}, { passive: true, once: true });

// ─── VIDEO SCRUB ───────────────────────────────────────────────────
function initVideoScrub() {
  // currentTime scrub — driven by scroll position
  ScrollTrigger.create({
    trigger: '#video-section',
    start: 'top top',
    end: 'bottom bottom',
    scrub: 0.5,
    onUpdate: self => {
      if (video.readyState >= 2 && video.duration) {
        video.currentTime = self.progress * video.duration;
      }
    }
  });

  // ─── Text overlay timeline (synced to same scroll range) ──────────
  const tl = gsap.timeline({
    scrollTrigger: {
      trigger: '#video-section',
      start: 'top top',
      end: 'bottom bottom',
      scrub: 0.4,
    }
  });

  // Text 1: product name — fade in (0%), hold, fade out (25%)
  tl.to('.vid-text-1', { opacity: 1, y: 0, duration: 0.08, ease: 'power2.out' }, 0.02)
    .to('.vid-text-1', { opacity: 0, y: -15, duration: 0.06 }, 0.24);

  // Text 2: stat callout — fade in (38%), hold, fade out (70%)
  tl.fromTo('.vid-text-2',
    { opacity: 0, y: 20 },
    { opacity: 1, y: 0, duration: 0.08, ease: 'power2.out' }, 0.38)
    .to('.vid-text-2', { opacity: 0, y: -15, duration: 0.07 }, 0.68);

  // Text 3: closer — fade in (82%), hold to end
  tl.fromTo('.vid-text-3',
    { opacity: 0, y: 20 },
    { opacity: 1, y: 0, duration: 0.08, ease: 'power2.out' }, 0.82)
    .to('.vid-text-3', { opacity: 0, duration: 0.04 }, 0.97);
}

// Init after metadata loads (needed to know video.duration)
if (video.readyState >= 1) {
  initVideoScrub();
} else {
  video.addEventListener('loadedmetadata', initVideoScrub, { once: true });
}

// ─── SECTION ANIMATE-IN ────────────────────────────────────────────
gsap.utils.toArray('.animate-in').forEach(el => {
  gsap.to(el, {
    scrollTrigger: {
      trigger: el,
      start: 'top 85%',
      toggleActions: 'play none none none',
    },
    opacity: 1,
    y: 0,
    duration: 0.75,
    ease: 'power2.out',
  });
});

// Stagger cards within the ingredient grid
ScrollTrigger.batch('.ingredient-grid .ingredient-card', {
  start: 'top 85%',
  onEnter: els => {
    gsap.to(els, {
      opacity: 1,
      y: 0,
      duration: 0.65,
      stagger: 0.1,
      ease: 'power2.out',
      overwrite: 'auto',
    });
  },
});

// Stagger stats
ScrollTrigger.batch('.stat', {
  start: 'top 85%',
  onEnter: els => {
    gsap.to(els, {
      opacity: 1,
      y: 0,
      duration: 0.6,
      stagger: 0.12,
      ease: 'power2.out',
      overwrite: 'auto',
    });
  },
});

// ─── STAT COUNTER ANIMATION ────────────────────────────────────────
document.querySelectorAll('.stat-num').forEach(el => {
  const target = parseFloat(el.dataset.target);
  const decimals = target % 1 !== 0 ? 2 : 0;
  const obj = { val: 0 };

  ScrollTrigger.create({
    trigger: el.closest('.stat'),
    start: 'top 85%',
    once: true,
    onEnter: () => {
      gsap.to(obj, {
        val: target,
        duration: 2,
        ease: 'power2.out',
        onUpdate: () => {
          el.textContent = obj.val.toFixed(decimals);
        },
      });
    },
  });
});
