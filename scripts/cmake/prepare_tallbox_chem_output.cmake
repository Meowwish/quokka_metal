if(NOT DEFINED OUTDIR)
  message(FATAL_ERROR "OUTDIR is required")
endif()

file(REMOVE_RECURSE "${OUTDIR}")
file(MAKE_DIRECTORY "${OUTDIR}")
