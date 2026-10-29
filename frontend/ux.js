const menuButton=document.getElementById('menuToggle');
const mainNavigation=document.getElementById('mainNavigation');
function setMenuOpen(open){
  mainNavigation.classList.toggle('open',open);
  menuButton.setAttribute('aria-expanded',String(open));
  menuButton.setAttribute('aria-label',open?'Đóng menu':'Mở menu');
  menuButton.textContent=open?'×':'☰';
}
menuButton.addEventListener('click',()=>setMenuOpen(menuButton.getAttribute('aria-expanded')!=='true'));
mainNavigation.querySelectorAll('a,button').forEach(item=>item.addEventListener('click',()=>setMenuOpen(false)));
document.getElementById('favoritesBtn').addEventListener('click',showFavorites);
document.getElementById('ordersBtn').addEventListener('click',showOrders);
document.getElementById('pointsBtn').addEventListener('click',showPoints);
document.getElementById('mobileFavoritesBtn').addEventListener('click',showFavorites);
document.getElementById('mobileOrdersBtn').addEventListener('click',showOrders);
document.getElementById('mobilePointsBtn').addEventListener('click',showPoints);
document.addEventListener('focusin',event=>{
  if(event.target.matches('[data-status]'))event.target.dataset.previousStatus=event.target.value;
},true);
document.addEventListener('change',event=>{
  const select=event.target.closest('[data-status]');
  if(select&&select.value==='Đã hủy'&&!window.confirm('Bạn có chắc muốn hủy đơn hàng này?')){
    event.preventDefault();event.stopImmediatePropagation();select.value=select.dataset.previousStatus||'Đang xử lý';
  }
},true);
document.addEventListener('click',event=>{
  const reject=event.target.closest('[data-review="rejected"]');
  if(reject&&!window.confirm('Từ chối sản phẩm này? Sản phẩm sẽ không được hiển thị trong danh mục.')){
    event.preventDefault();event.stopImmediatePropagation();
  }
},true);
