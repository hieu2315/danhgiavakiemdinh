(function () {
  const fallbackImage = '/assets/product-fallback.svg';
  const products = new Map();

  async function api(path) {
    const response = await fetch(path, { credentials: 'same-origin' });
    let data = {};
    try {
      data = await response.json();
    } catch {}
    if (!response.ok) throw new Error(data && data.error ? data.error : `Yêu cầu thất bại (${response.status})`);
    return data;
  }

  function esc(value) {
    return String(value).replace(/[&<>"']/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[character]);
  }

  function money(value) {
    return new Intl.NumberFormat('vi-VN').format(value) + 'đ';
  }

  function makeSection(id, title) {
    const section = document.createElement('section');
    section.id = id;
    section.className = 'section recommendation-section hidden';
    section.dataset.recommendationRoot = 'true';
    section.setAttribute('aria-labelledby', `${id}Title`);
    section.innerHTML = `<div class="section-head"><div><div class="eyebrow">GỢI Ý THEO LUẬT KẾT HỢP</div><h2 id="${id}Title">${title}</h2></div></div><div class="recommendation-status" role="status" aria-live="polite"></div><div class="product-grid recommendation-grid"></div>`;
    return section;
  }

  function renderCard(product) {
    products.set(String(product.id), product);
    const image = product.image || fallbackImage;
    const href = `/p/${encodeURIComponent(product.slug || product.id)}`;
    return `<article class="product-card recommendation-card"><a class="recommendation-image-link" href="${esc(href)}" aria-label="Xem ${esc(product.name)}"><div class="product-image recommendation-image"><img class="product-photo" data-recommendation-image src="${esc(image)}" alt="${esc(product.name)}" loading="lazy"></div></a><div class="product-info"><div class="condition">${esc(product.condition || 'Sản phẩm tuần hoàn')}</div><h3><a class="product-title" href="${esc(href)}">${esc(product.name)}</a></h3><span class="recommendation-reason">${esc(product.reason)}</span><div class="product-bottom"><span class="price">${money(product.price)}</span><span class="recommendation-actions"><a class="small-button" href="${esc(href)}" aria-label="Xem ${esc(product.name)}">Xem</a><button type="button" class="small-button" data-recommendation-add="${esc(product.id)}" aria-label="Thêm ${esc(product.name)} vào giỏ hàng" ${Number(product.stock) <= 0 ? 'disabled' : ''}>Thêm giỏ</button></span></div></div></article>`;
  }

  async function load(section, options, force) {
    if (!section) return;
    const context = options.context || 'home';
    const cartIds = context === 'cart' ? [...new Set(options.cartIds || [])].slice(0, 20) : [];
    const key = `${context}:${options.productId || ''}:${cartIds.join(',')}`;
    if (!force && (section.dataset.loading === 'true' || section.dataset.loadedKey === key)) return;

    section.dataset.loading = 'true';
    section.dataset.options = JSON.stringify({ context, productId: options.productId || '', cartIds });
    section.classList.remove('hidden');
    section.setAttribute('aria-busy', 'true');
    const status = section.querySelector('.recommendation-status');
    const grid = section.querySelector('.recommendation-grid');
    status.textContent = 'Đang tải gợi ý…';
    grid.replaceChildren();
    try {
      let path;
      if (context === 'product') {
        path = `/api/recommendations/${encodeURIComponent(options.productId)}`;
      } else {
        const query = new URLSearchParams({ context, limit: '8' });
        if (context === 'cart') query.set('cart', cartIds.join(','));
        path = `/api/recommendations?${query.toString()}`;
      }
      const data = await api(path);
      const items = Array.isArray(data.items) ? data.items : [];
      section.dataset.loadedKey = key;
      if (context === 'home') {
        const heading = section.querySelector('h2');
        heading.textContent = data.method === 'hybrid-rule-based' ? 'Gợi ý cho bạn' : 'Đang được quan tâm';
      }
      if (!items.length) {
        status.textContent = '';
        section.classList.add('hidden');
        return;
      }
      status.textContent = '';
      grid.innerHTML = items.map(renderCard).join('');
      grid.querySelectorAll('[data-recommendation-image]').forEach(imageElement => {
        imageElement.addEventListener('error', () => {
          imageElement.src = fallbackImage;
        }, { once: true });
      });
    } catch (error) {
      const message = error instanceof TypeError ? 'Không kết nối được máy chủ.' : error.message;
      status.textContent = `Chưa tải được gợi ý: ${message} `;
      const retry = document.createElement('button');
      retry.className = 'small-button';
      retry.type = 'button';
      retry.dataset.recommendationRetry = 'true';
      retry.textContent = 'Thử lại';
      status.append(retry);
    } finally {
      section.dataset.loading = 'false';
      section.setAttribute('aria-busy', 'false');
    }
  }

  function addToCart(product, section) {
    const status = section.querySelector('.recommendation-status');
    if (window.ReLoopAddToCart) {
      if (window.ReLoopAddToCart(product)) status.textContent = `Đã thêm ${product.name} vào giỏ hàng.`;
      return;
    }
    let saved = {};
    try {
      saved = JSON.parse(localStorage.getItem('reloop-market-v1')) || {};
    } catch {
      saved = {};
    }
    const cart = Array.isArray(saved.cart) ? saved.cart : [];
    const existing = cart.find(item => item.id === product.id);
    if (Number(product.stock) <= 0 || (existing && existing.qty >= Number(product.stock))) {
      status.textContent = 'Số lượng trong kho không đủ.';
      return;
    }
    if (existing) existing.qty += 1;
    else cart.push({ id: product.id, qty: 1 });
    try {
      localStorage.setItem('reloop-market-v1', JSON.stringify({ ...saved, cart }));
    } catch {
      status.textContent = 'Không thể lưu giỏ hàng trên thiết bị này.';
      return;
    }
    window.dispatchEvent(new CustomEvent('reloop:cart-updated', { detail: { cart } }));
    status.textContent = `Đã thêm ${product.name} vào giỏ hàng.`;
  }

  document.addEventListener('click', event => {
    const retry = event.target.closest('[data-recommendation-retry]');
    if (retry) {
      const section = retry.closest('[data-recommendation-root]');
      if (section) {
        const options = JSON.parse(section.dataset.options || '{}');
        load(section, options, true);
      }
      return;
    }
    const add = event.target.closest('[data-recommendation-add]');
    if (add) {
      const product = products.get(add.dataset.recommendationAdd);
      const section = add.closest('[data-recommendation-root]');
      if (product && section) addToCart(product, section);
    }
  });

  document.addEventListener('click', () => {
    window.setTimeout(attachCartRecommendations, 0);
  });

  function attachCartRecommendations() {
    const checkout = document.getElementById('checkoutBtn');
    if (!checkout || document.getElementById('cartRecommendations')) return;
    const section = makeSection('cartRecommendations', 'Thường được mua cùng');
    section.classList.add('cart-recommendations');
    checkout.before(section);
    let cart = [];
    try {
      cart = JSON.parse(localStorage.getItem('reloop-market-v1'))?.cart || [];
    } catch {}
    load(section, { context: 'cart', cartIds: cart.map(item => item.id) }, false);
  }

  const productSection = document.getElementById('products');
  if (productSection) {
    const homeSection = makeSection('homeRecommendations', 'Đang được quan tâm');
    productSection.after(homeSection);
    const grid = document.getElementById('productGrid');
    const loadHome = () => load(homeSection, { context: 'home' }, false);
    if (grid.getAttribute('aria-busy') === 'false') loadHome();
    else {
      const observer = new MutationObserver(() => {
        if (grid.getAttribute('aria-busy') === 'false') {
          observer.disconnect();
          loadHome();
        }
      });
      observer.observe(grid, { attributes: true, attributeFilter: ['aria-busy'] });
    }
  }

  const productDetail = document.getElementById('productRecommendations');
  if (productDetail) {
    load(productDetail, { context: 'product', productId: productDetail.dataset.productId }, false);
  }

})();
