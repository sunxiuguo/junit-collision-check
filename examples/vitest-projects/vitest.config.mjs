export default {
  test: {
    reporters: [['junit', {
      outputFile: 'generated.xml',
      classnameTemplate: '{displayName}:{filename}',
    }]],
    projects: [
      { test: { name: 'project-a', globals: true, include: ['same.test.js'] } },
      { test: { name: 'project-b', globals: true, include: ['same.test.js'] } },
    ],
  },
}
