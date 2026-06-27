export function createAdminMountProps(initialProps = {}) {
  const props = $state({ ...initialProps });

  return {
    props,
    update(nextProps = {}) {
      Object.assign(props, nextProps);
    },
  };
}
