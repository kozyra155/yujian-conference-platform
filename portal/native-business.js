(() => {
 const root = document.querySelector('.meet-native-business');
 if (!root) return;
 // Scroll wide native tables within the card, without moving React roots or form fields.
 root.querySelectorAll('.meet-business-content table').forEach(table => {
  if (table.closest('.table-wrapper, .i-table-responsive, .meet-business-table')) return;
  const wrapper = document.createElement('div');
  wrapper.className = 'meet-business-table';
  wrapper.tabIndex = 0;
  wrapper.setAttribute('role', 'region');
  wrapper.setAttribute('aria-label', 'Scrollable table / 可横向滚动的表格');
  table.before(wrapper);
  wrapper.append(table);
 });
})();
