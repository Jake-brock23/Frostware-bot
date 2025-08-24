// Enhanced JavaScript for Frostware Utility Bot Website

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Parallax effect for hero section
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const hero = document.querySelector('.hero');
        if (hero) {
            hero.style.transform = `translateY(${scrolled * 0.5}px)`;
        }
    });

    // Animated counter for metrics
    function animateCounter(element, target, duration = 2000) {
        const start = 0;
        const range = target - start;
        const startTime = performance.now();

        function updateCounter(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const current = Math.floor(progress * range + start);
            
            element.textContent = current;
            
            if (progress < 1) {
                requestAnimationFrame(updateCounter);
            } else {
                element.textContent = target;
            }
        }
        
        requestAnimationFrame(updateCounter);
    }

    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                
                // Animate counters when status section comes into view
                if (entry.target.classList.contains('status-section')) {
                    const metrics = entry.target.querySelectorAll('.metric');
                    metrics.forEach(metric => {
                        const target = parseInt(metric.textContent);
                        if (!isNaN(target)) {
                            animateCounter(metric, target);
                        }
                    });
                }
            }
        });
    }, observerOptions);

    // Observe sections for animations
    document.querySelectorAll('section').forEach(section => {
        observer.observe(section);
    });

    // Dynamic particle effect
    function createParticle() {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.cssText = `
            position: fixed;
            width: 4px;
            height: 4px;
            background: linear-gradient(45deg, #00d4ff, #9000ff);
            border-radius: 50%;
            pointer-events: none;
            z-index: 1;
            opacity: 0.7;
        `;
        
        const x = Math.random() * window.innerWidth;
        const y = window.innerHeight;
        
        particle.style.left = x + 'px';
        particle.style.top = y + 'px';
        
        document.body.appendChild(particle);
        
        const animation = particle.animate([
            {
                transform: 'translateY(0px) scale(1)',
                opacity: 0.7
            },
            {
                transform: `translateY(-${window.innerHeight + 100}px) scale(0)`,
                opacity: 0
            }
        ], {
            duration: Math.random() * 3000 + 2000,
            easing: 'linear'
        });
        
        animation.onfinish = () => {
            particle.remove();
        };
    }

    // Create particles periodically
    setInterval(createParticle, 300);

    // Status monitoring with auto-refresh
    function updateBotStatus() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                // Update status indicator
                const statusDot = document.querySelector('.status-dot');
                const statusText = document.querySelector('.status-text');
                
                if (data.online) {
                    statusDot.className = 'status-dot online';
                    statusText.textContent = 'Online';
                } else {
                    statusDot.className = 'status-dot offline';
                    statusText.textContent = 'Offline';
                }
                
                // Update metrics
                const metrics = document.querySelectorAll('.metric');
                if (metrics.length >= 3) {
                    metrics[0].textContent = data.guilds || '1';
                    metrics[1].textContent = data.permitted_users || '0';
                    metrics[2].textContent = (data.latency || '0') + 'ms';
                }
            })
            .catch(error => {
                console.log('Status update failed:', error);
                const statusDot = document.querySelector('.status-dot');
                const statusText = document.querySelector('.status-text');
                statusDot.className = 'status-dot offline';
                statusText.textContent = 'Offline';
            });
    }

    // Update status every 30 seconds
    setInterval(updateBotStatus, 30000);
    
    // Initial status update
    updateBotStatus();

    // Enhanced hover effects for cards
    document.querySelectorAll('.status-card, .feature-card, .command-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // Typing effect for hero title
    function typeWriter(element, text, speed = 100) {
        let i = 0;
        element.textContent = '';
        
        function type() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                setTimeout(type, speed);
            }
        }
        
        type();
    }

    // Add glow effect on scroll
    window.addEventListener('scroll', () => {
        const scrollPercent = window.scrollY / (document.body.scrollHeight - window.innerHeight);
        const hue = scrollPercent * 360;
        
        document.documentElement.style.setProperty('--dynamic-hue', hue);
    });
});

// Add CSS animation classes
const style = document.createElement('style');
style.textContent = `
    .animate-in {
        animation: slideInUp 0.8s ease-out forwards;
    }
    
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(50px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .particle {
        animation: float-up 3s linear forwards;
    }
    
    @keyframes float-up {
        0% {
            opacity: 0.7;
            transform: translateY(0) scale(1);
        }
        100% {
            opacity: 0;
            transform: translateY(-100vh) scale(0);
        }
    }
`;

document.head.appendChild(style);
