export default {
  test: {
    name: process.env.DEMO_PROJECT || 'matrix',
    reporters: [['junit', {classnameTemplate: process.env.DEMO_CLASSNAME || undefined}]]
  }
}
