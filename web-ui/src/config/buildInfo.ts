export const formatBuildLabel = (releaseVersion: string, gitSha: string): string => {
  const normalizedSha = gitSha.trim() || 'unknown'
  const normalizedVersion = releaseVersion.trim()

  if (!normalizedVersion) {
    return normalizedSha
  }

  return `v${normalizedVersion} (${normalizedSha})`
}

export const appBuildLabel = formatBuildLabel(__APP_RELEASE_VERSION__, __APP_GIT_SHA__)
