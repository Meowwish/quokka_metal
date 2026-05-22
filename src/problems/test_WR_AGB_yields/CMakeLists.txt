if(AMReX_SPACEDIM EQUAL 3)
    set(JOB_NAME test_WR_AGB_yields)

    add_executable(${JOB_NAME} ${JOB_NAME}.cpp ${QuokkaObjSources})
    if(AMReX_GPU_BACKEND MATCHES "CUDA")
        setup_target_for_cuda_compilation(${JOB_NAME})
    endif()

    add_test(
        NAME ${JOB_NAME}
        COMMAND ${JOB_NAME} ../inputs/${JOB_NAME}.toml ${QuokkaTestParams}
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}/tests)
    add_test(
        NAME ${JOB_NAME}_validate
        COMMAND python3 ${CMAKE_SOURCE_DIR}/scripts/validate_chemical_yields.py
            --case wr_agb
            --plotdir ${CMAKE_SOURCE_DIR}/tests/${JOB_NAME}
            --yield-root ${CMAKE_SOURCE_DIR}/extern/yields
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})
    set_tests_properties(${JOB_NAME} PROPERTIES FIXTURES_SETUP ${JOB_NAME}_fixture)
    set_tests_properties(${JOB_NAME}_validate PROPERTIES FIXTURES_REQUIRED ${JOB_NAME}_fixture)

endif()
